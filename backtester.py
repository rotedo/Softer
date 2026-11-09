"""Backtester: trusted engine + sandboxed signal code. The sandbox only returns signals; the engine computes the result."""
import ast, json, subprocess, sys
import aggregator as a

BANNED = {"open", "exec", "eval", "compile", "getattr", "setattr", "delattr", "__import__", "globals", "locals", "vars", "input", "breakpoint", "memoryview", "type", "super", "object"}

RUNNER = r'''
import sys, json, ast, resource, math
resource.setrlimit(resource.RLIMIT_CPU, (5, 5))
resource.setrlimit(resource.RLIMIT_AS, (768 * 2**20, 768 * 2**20))
d = json.loads(sys.stdin.read())
code, c, f = d["code"], d["c"], d["f"]
BANNED = set(d["banned"])
t = ast.parse(code)
for n in ast.walk(t):
    if isinstance(n, (ast.Import, ast.ImportFrom)): raise SystemExit("imports are not allowed")
    if isinstance(n, ast.Attribute) and n.attr.startswith("_"): raise SystemExit("underscore attributes are not allowed")
    if isinstance(n, ast.Name) and (n.id in BANNED or n.id.startswith("__")): raise SystemExit("name not allowed: " + n.id)
def sma(x, p):
    return [None if i + 1 < p else sum(x[i + 1 - p:i + 1]) / p for i in range(len(x))]
def ema(x, p):
    k, o, e = 2 / (p + 1), [], None
    for v in x:
        e = v if e is None else v * k + e * (1 - k)
        o.append(e)
    return o
def highest(x, p):
    return [None if i + 1 < p else max(x[i + 1 - p:i + 1]) for i in range(len(x))]
def lowest(x, p):
    return [None if i + 1 < p else min(x[i + 1 - p:i + 1]) for i in range(len(x))]
def atr(c, p=14):
    tr = [c[i]["h"] - c[i]["l"] if i == 0 else max(c[i]["h"] - c[i]["l"], abs(c[i]["h"] - c[i - 1]["c"]), abs(c[i]["l"] - c[i - 1]["c"])) for i in range(len(c))]
    return sma(tr, p)
safe = {k: __builtins__.__dict__[k] if hasattr(__builtins__, "__dict__") else __builtins__[k] for k in
        ("abs", "min", "max", "sum", "len", "range", "enumerate", "zip", "round", "float", "int", "bool", "list", "dict", "tuple", "sorted", "reversed", "any", "all", "map", "filter", "isinstance", "str", "set", "True", "False", "None")}
env = {"__builtins__": safe, "sma": sma, "ema": ema, "highest": highest, "lowest": lowest, "atr": atr, "math": math}
exec(compile(t, "<strategy>", "exec"), env)
s = env["signals"](c, f)
out = [int(x) if x in (-1, 0, 1) else 0 for x in s][:len(c)]
print(json.dumps(out))
'''


def features(cs):
    f = {"delta": [], "bp": [], "cvd": [], "body": [], "upper": [], "lower": []}
    for c in cs:
        f["delta"].append(c.get("delta") or 0)
        f["bp"].append(c.get("bp") if c.get("bp") is not None else 0.5)
        f["cvd"].append(c.get("cvd") or 0)
        f["body"].append(abs(c["c"] - c["o"]))
        f["upper"].append(c["h"] - max(c["o"], c["c"]))
        f["lower"].append(min(c["o"], c["c"]) - c["l"])
    return f


def run_code(code, cs, f):
    if len(code) > 20000:
        raise ValueError("code too long")
    try:
        ast.parse(code)
    except SyntaxError as e:
        raise ValueError(f"syntax error: {e}")
    import resource  # noqa  (only to fail early on non-unix)
    p = subprocess.run([sys.executable, "-I", "-c", RUNNER], input=json.dumps({"code": code, "c": cs, "f": f, "banned": sorted(BANNED)}),
                       capture_output=True, text=True, timeout=10)
    if p.returncode != 0:
        raise ValueError("strategy rejected/failed: " + ((p.stderr or "").strip().splitlines() or ["error"])[-1][:200])
    return json.loads(p.stdout)


def _ema(x, p):
    k, e, o = 2 / (p + 1), None, []
    for v in x:
        e = v if e is None else v * k + e * (1 - k)
        o.append(e)
    return o


def builtin(name, cs, f, params):
    n, s = len(cs), [0] * len(cs)
    if name == "ema":
        fa, sl = _ema([c["c"] for c in cs], int(params.get("fast", 9))), _ema([c["c"] for c in cs], int(params.get("slow", 21)))
        for i in range(1, n):
            s[i] = 1 if fa[i - 1] <= sl[i - 1] and fa[i] > sl[i] else -1 if fa[i - 1] >= sl[i - 1] and fa[i] < sl[i] else 0
    elif name == "delta":  # 3 candles of the same delta sign, then flip
        for i in range(3, n):
            d = f["delta"]
            if d[i] > 0 and all(x < 0 for x in d[i - 3:i]):
                s[i] = 1
            elif d[i] < 0 and all(x > 0 for x in d[i - 3:i]):
                s[i] = -1
    elif name == "sweep":
        for i in range(n):
            s[i] = cs[i].get("sw") or 0
    else:
        raise ValueError("unknown strategy " + name)
    return s


def engine(cs, f, sig, cap=1000.0, lev=5.0, sl=0.8, tp=2.0, fee=0.05):
    """signals per candle; entry at NEXT open; SL before TP inside a candle; loss capped at equity."""
    sl_eff = min(sl, 100 / lev - 0.5)
    if sl_eff <= 0:
        raise ValueError("leverage too high for this stop")
    eq, peak, mdd, trades, curve, pos = cap, cap, 0.0, [], [], None
    for i in range(1, len(cs)):
        c = cs[i]
        if pos:
            d, e = pos["dir"], pos["entry"]
            stop, tgt = e * (1 - d * sl_eff / 100), e * (1 + d * tp / 100)
            hit = None
            if (d == 1 and c["l"] <= stop) or (d == -1 and c["h"] >= stop):
                hit = stop
            elif (d == 1 and c["h"] >= tgt) or (d == -1 and c["l"] <= tgt):
                hit = tgt
            elif sig[i - 1] == -d:  # opposite signal: exit at this open
                hit = c["o"]
            if hit is not None:
                mv = d * (hit - e) / e
                pnl = max(-eq, eq * lev * (mv - 2 * fee / 100))
                eq += pnl
                trades.append({**pos["ctx"], "t_in": pos["t"], "t_out": c["t"], "dir": d, "entry": e, "exit": hit, "pnl": round(pnl, 2), "ret_pct": round(pnl / (eq - pnl) * 100, 2)})
                pos = None
        if not pos and sig[i - 1] in (1, -1) and eq > 0:
            j = i - 1
            pos = {"dir": sig[j], "entry": c["o"], "t": c["t"], "ctx": {"delta_aligned": f["delta"][j] * sig[j] > 0, "bp": round(f["bp"][j], 2),
                   "wick_ratio": round((f["upper"][j] + f["lower"][j]) / (f["body"][j] or 1e-9), 2)}}
        peak = max(peak, eq)
        mdd = max(mdd, (peak - eq) / peak * 100 if peak else 0)
        curve.append([c["t"], round(eq, 2)])
    w = [t for t in trades if t["pnl"] > 0]
    ls = [t for t in trades if t["pnl"] <= 0]
    gp, gl = sum(t["pnl"] for t in w), -sum(t["pnl"] for t in ls)
    stats = {"trades": len(trades), "win_rate": round(len(w) / len(trades) * 100, 1) if trades else 0, "net": round(eq - cap, 2),
             "return_pct": round((eq - cap) / cap * 100, 2), "max_dd_pct": round(mdd, 2), "profit_factor": round(gp / gl, 2) if gl else None,
             "avg_win": round(gp / len(w), 2) if w else 0, "avg_loss": round(-gl / len(ls), 2) if ls else 0}
    return {"stats": stats, "trades": trades[-200:], "curve": curve, "explain": explain(trades)}


def explain(trades):
    if len(trades) < 6:
        return "Too few trades to explain anything (need 6+)."
    w, l = [t for t in trades if t["pnl"] > 0], [t for t in trades if t["pnl"] <= 0]
    if not w or not l:
        return "All trades had the same result; nothing to compare."
    avg = lambda xs, k: sum(x[k] for x in xs) / len(xs)
    al = lambda xs: sum(1 for x in xs if x["delta_aligned"]) / len(xs) * 100
    return (f"Winners: delta agreed with trade in {al(w):.0f}% vs losers {al(l):.0f}%. Wick/body at entry: winners {avg(w, 'wick_ratio'):.1f}, losers {avg(l, 'wick_ratio'):.1f}. "
            f"Buy ratio at entry: winners {avg(w, 'bp'):.2f}, losers {avg(l, 'bp'):.2f}. Small sample = weak evidence.")


def run(strategy="ema", params=None, sym="BTCUSDT", tf="15m", n=300, cap=1000, lev=5, sl=0.8, tp=2.0, fee=0.05, code=None):
    b = a.bundle(sym, tf, int(min(n, 1000)))
    cs = b["candles"]
    if len(cs) < 30:
        raise ValueError("not enough candles collected yet")
    f = features(cs)
    sig = run_code(code, cs, f) if strategy == "code" else builtin(strategy, cs, f, params or {})
    sig = (sig + [0] * len(cs))[:len(cs)]
    r = engine(cs, f, sig, float(cap), float(lev), float(sl), float(tp), float(fee))
    r.update(sym=sym, tf=tf, approx=b.get("approx", False), candles=len(cs))
    return r
