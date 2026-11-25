"""Screener: every few minutes runs your Pine-style scripts on the Tier 1 + Tier 2 coins (CoinDCX pairs that pass your
liquidity filter; the candle / order-flow data itself comes merged from all exchanges). A script that fires -> Telegram.

A script is Python in the same safe sandbox as the backtester. It must define signals(c, f) and return a list with one
number per candle: 1 = long setup, -1 = short setup, 0 = nothing. Only the last CLOSED candle is checked.
  c[i] = {t,o,h,l,c,v,delta,bp,cvd,...}   f = {delta,bp,cvd,body,upper,lower}   helpers: sma ema highest lowest atr math
"""
import asyncio, json, logging, time
import aggregator as a, archive, backtester as bt, store

DEFAULT_SCRIPTS = [
    {"id": 1, "name": "Pump candle", "tf": "15m", "on": True, "code": '''# Big green/red candle: range above 3x ATR and closes near its extreme, with volume above 3x average
def signals(c, f):
    n = len(c)
    out = [0] * n
    a = atr(c, 14)
    for i in range(21, n):
        if a[i - 1] is None:
            continue
        rng = c[i]["h"] - c[i]["l"]
        vols = [(c[j].get("v") or 0) for j in range(i - 20, i)]
        avg = sum(vols) / 20
        if rng > 3 * a[i - 1] and avg > 0 and (c[i].get("v") or 0) > 3 * avg:
            if c[i]["c"] > c[i]["o"] and c[i]["c"] >= c[i]["h"] - 0.25 * rng:
                out[i] = 1
            elif c[i]["c"] < c[i]["o"] and c[i]["c"] <= c[i]["l"] + 0.25 * rng:
                out[i] = -1
    return out
'''},
    {"id": 2, "name": "Hidden buying/selling", "tf": "15m", "on": False, "code": '''# Order flow: red candle but buyers dominated (delta strongly positive) = hidden buying (long); green candle with strong negative delta = hidden selling (short)
def signals(c, f):
    n = len(c)
    out = [0] * n
    d = f["delta"]
    for i in range(21, n):
        avg = sum(abs(d[j]) for j in range(i - 20, i)) / 20
        if avg == 0:
            continue
        if c[i]["c"] < c[i]["o"] and d[i] > 2 * avg:
            out[i] = 1
        elif c[i]["c"] > c[i]["o"] and d[i] < -2 * avg:
            out[i] = -1
    return out
'''},
    {"id": 3, "name": "Breakout with delta", "tf": "15m", "on": False, "code": '''# Close above the highest high of the last 20 candles with positive delta (long); below the lowest low with negative delta (short)
def signals(c, f):
    n = len(c)
    out = [0] * n
    hi = highest([x["h"] for x in c], 20)
    lo = lowest([x["l"] for x in c], 20)
    for i in range(21, n):
        if hi[i - 1] is None:
            continue
        if c[i]["c"] > hi[i - 1] and f["delta"][i] > 0:
            out[i] = 1
        elif c[i]["c"] < lo[i - 1] and f["delta"][i] < 0:
            out[i] = -1
    return out
'''},
]
SENT = {}  # (script id, sym, candle t) -> True   (no repeat alerts)
LAST = {"run": None, "checked": 0, "error": ""}


RENKO_CODE = r'''# Renko (brick = ATR 14) on this timeframe: alert when a brick closes above its 9-EMA (fresh cross up)
ONLY_CROSS = True   # False = alert on every brick that closes above the 9-EMA
def signals(c, f):
    n = len(c)
    out = [0] * n
    a = atr(c, 14)
    if n < 40 or a[n - 2] is None or a[n - 2] <= 0:
        return out
    size = a[n - 2]
    last = c[0]["c"]
    d = 0
    bricks = []
    for i in range(1, n):
        p = c[i]["c"]
        while True:
            if d >= 0 and p >= last + size:
                last = last + size
                d = 1
            elif d <= 0 and p <= last - size:
                last = last - size
                d = -1
            elif d == 1 and p <= last - 2 * size:
                last = last - 2 * size
                d = -1
            elif d == -1 and p >= last + 2 * size:
                last = last + 2 * size
                d = 1
            else:
                break
            bricks.append([last, i])
    if len(bricks) < 12:
        return out
    e = ema([b[0] for b in bricks], 9)
    for k in range(10, len(bricks)):
        above = bricks[k][0] > e[k]
        was = bricks[k - 1][0] > e[k - 1]
        if above and (was is False or not ONLY_CROSS):
            out[bricks[k][1]] = 1
    return out
'''
PRESETS = [{"id": 101 + i, "name": f"Renko 9 EMA ({tf})", "tf": tf, "on": True, "uni": "tier2", "code": RENKO_CODE}
           for i, tf in enumerate(["5m", "15m", "1H", "4H", "1D"])]


def scripts():
    s = store.scripts_get()
    if s is None:
        s = list(DEFAULT_SCRIPTS)
        store.scripts_set(s)
    if not store.kv_get("presets_renko_v1"):  # added once; delete them if you do not want them
        s = list(s) + [p for p in PRESETS if not any(x["id"] == p["id"] for x in s)]
        store.scripts_set(s)
        store.kv_set("presets_renko_v1", True)
    return s


def cfg():
    base = {"every_min": 5, "ai": False, "universe": "tier1",
            "spike": {"on": True, "pct": 3.0, "mins": 5, "cooldown": 10}}
    got = store.kv_get("screener_cfg", {}) or {}
    return base | got | {"spike": base["spike"] | (got.get("spike") or {})}


def universe():
    """coins the screener watches. tier1 = only your liquidity filter (CoinDCX depth scan); tier2 = also needs a big recent range"""
    rows = a.tiers() if cfg().get("universe") == "tier2" else a.tier1()
    return [t["sym"] for t in rows]


def _uni(v):
    v = str(v or "").strip().lower().replace(" ", "")
    return "tier2" if v in ("tier2", "t2", "2") else "all" if v in ("all", "both", "tier1+2", "tier1,tier2") else ""


def save_script(d):
    code, name = str(d.get("code") or ""), str(d.get("name") or "My script").strip()[:40]
    b = a.bundle("BTCUSDT", "15m", 120)["candles"]
    if len(b) >= 30:
        bt.run_code(code, b, bt.features(b))  # raises ValueError with the reason if the script is bad
    ss = scripts()
    if d.get("id") and any(x["id"] == int(d["id"]) for x in ss):
        for x in ss:
            if x["id"] == int(d["id"]):
                x.update(name=name, code=code, tf=str(d.get("tf") or x["tf"]).strip(), on=bool(d.get("on", x["on"])), uni=_uni(d.get("uni")))
        i = int(d["id"])
    else:
        i = max([x["id"] for x in ss] + [0]) + 1
        ss.append({"id": i, "name": name, "code": code, "tf": str(d.get("tf") or "15m").strip(), "on": bool(d.get("on", False)), "uni": _uni(d.get("uni"))})
    store.scripts_set(ss)
    return i


def delete_script(i):
    store.scripts_set([x for x in scripts() if x["id"] != int(i)])


def test_script(code, sym="BTCUSDT", tf="15m", n=200):
    b = a.bundle(sym, tf, n)["candles"]
    if len(b) < 30:
        raise ValueError("not enough candles collected yet for " + sym)
    sig = bt.run_code(code, b, bt.features(b))
    hits = [{"t": b[i]["t"], "side": "long" if s > 0 else "short", "price": b[i]["c"]} for i, s in enumerate(sig) if s]
    return {"sym": sym, "candles": len(b), "signals": len(hits), "last": hits[-5:]}


def recent():
    return store.kv_get("alerts", []) or []


def _push(al):
    store.kv_set("alerts", ([al] + recent())[:60])


def _ai_note(al):
    try:
        import agents, llm
        llm.TL.task = "alerts"
        if not agents.keys():
            return ""
        s = analysis_summary(al["sym"], al["tf"])
        return agents.gemini(None, "You are a trading assistant. Use ONLY the data given. Reply in 2 short lines, Hindi/Hinglish. No guarantees.",
                             f"Alert: {al['script']} {al['side']} on {al['sym']} {al['tf']} at {al['price']}.\nData: {s}")[:400]
    except Exception:
        return ""


def analysis_summary(sym, tf):
    import analysis
    return json.dumps(analysis.summary(sym, tf), default=str)[:3000]


def run_once():
    """one full pass over Tier 1 + Tier 2 (blocking; the loop runs it in a thread). -> list of new alerts"""
    out, checked = [], 0
    syms = universe()
    t2 = None
    LAST.update(run=int(time.time() * 1000), error="")
    for sc in [x for x in scripts() if x.get("on")]:
        mine = syms
        if sc.get("uni") == "tier2":  # this script watches Tier 2 coins only
            if t2 is None:
                t2 = [t["sym"] for t in a.tiers() if t.get("tier") == 2]
            mine = t2
        elif sc.get("uni") == "all":
            mine = [t["sym"] for t in a.tiers()]
        for sym in mine:
            try:
                cs = a.bundle(sym, sc["tf"], 120)["candles"]
                if len(cs) < 40:
                    continue
                checked += 1
                sig = bt.run_code(sc["code"], cs, bt.features(cs))
                k = len(cs) - 2  # last closed candle
                if k < 0 or not sig[k]:
                    continue
                key = (sc["id"], sym, cs[k]["t"])
                if key in SENT:
                    continue
                SENT[key] = True
                al = {"ts": int(time.time() * 1000), "script": sc["name"], "sym": sym, "tf": sc["tf"], "side": "long" if sig[k] > 0 else "short", "price": cs[k]["c"]}
                msg = f"{'🟢' if sig[k] > 0 else '🔴'} {sym} {al['side'].upper()} | {sc['name']} | {sc['tf']} | price {al['price']}"
                if cfg().get("ai"):
                    note = _ai_note(al)
                    msg += ("\n" + note) if note else ""
                al["sent"] = archive.tg_message(msg)["ok"]
                _push(al)
                out.append(al)
            except Exception as e:
                LAST["error"] = f"{sc['name']} {sym}: {type(e).__name__}: {e}"[:160]
    if len(SENT) > 5000:
        SENT.clear()
    LAST["checked"] = checked
    return out


# ---------------------------------------------------------------- AI writes scripts for you
AI_SYSTEM = """You write trading screener scripts in Python. Output ONLY the code, no explanations, no markdown fences.
The script must define signals(c, f) and return a list with one number per candle: 1 = long setup, -1 = short setup, 0 = nothing.
Only the last closed candle is used. c[i] is a dict with keys t,o,h,l,c,v and sometimes delta,bp,cvd (delta/bp/cvd can be None).
f is a dict of lists: delta,bp,cvd,body,upper,lower. Available helpers (no import needed): sma ema highest lowest atr math.
sma/ema/highest/lowest take a list and a period and return a list with None where there is not enough data. atr(c, n) returns a list.
The second line must be a comment with the timeframe the user asked for, like `# TF: 5m` (allowed: 1m 5m 15m 1H 4H 1D or any like 7m, 2H; default 15m).\nRules: no imports, no file or network access, always guard against None, start loops after the longest lookback, start with a one-line comment saying what the script finds."""


def ai_script(prompt, name=None, tf="15m"):
    """AI writes a screener script from your plain-words idea, it is tested on real candles, saved OFF so you can read it first"""
    import agents, llm, re
    llm.TL.task = "scripts"
    prompt = str(prompt or "").strip()[:1500]
    if not prompt:
        raise ValueError("describe the setup you want")
    b = a.bundle("BTCUSDT", tf, 120)["candles"]
    msg, err = prompt, ""
    for _ in range(3):
        raw = agents.gemini(None, AI_SYSTEM, msg + (("\nYour previous code failed: " + err + "\nFix it.") if err else ""), timeout=60)
        code = raw.strip().strip("`").removeprefix("python").strip()
        try:
            if len(b) >= 30:
                bt.run_code(code, b, bt.features(b))
            else:
                import ast
                ast.parse(code)
            m = re.search(r"^#\s*TF:\s*(\S+)", code, re.M)
            tf = m.group(1) if m else tf
            first = code.splitlines()[0].lstrip("# ").strip() if code.startswith("#") else ""
            i = save_script({"name": (name or first or "AI script")[:40], "code": code, "tf": tf, "on": False})
            return {"id": i, "code": code}
        except Exception as e:
            err = str(e)[:300]
    raise ValueError("AI could not write a working script: " + err)


# ---------------------------------------------------------------- sudden spike detector (all coins, one request per minute)
PX = {}      # sym -> [(ts_ms, price, quote_vol_24h)]
COOL = {}    # sym -> ts of last spike alert
SPIKES = []  # recent spike alerts


def _fetch_tickers():
    import urllib.request
    req = urllib.request.Request("https://fapi.binance.com/fapi/v1/ticker/24hr", headers={"User-Agent": "orderflow-terminal/1.0"})
    return json.load(urllib.request.urlopen(req, timeout=10))


def spike_once(rows=None):
    """one pass: remember every coin's price; alert when a watched coin moved >= pct% inside `mins` minutes"""
    sp, now_ms, out = cfg()["spike"], int(time.time() * 1000), []
    rows = rows if rows is not None else _fetch_tickers()
    watch = set(universe())
    for r in rows:
        sym = r.get("symbol")
        if not sym:
            continue
        h = PX.setdefault(sym, [])
        h.append((now_ms, float(r["lastPrice"]), float(r.get("quoteVolume") or 0)))
        while h and now_ms - h[0][0] > 15 * 60000:
            h.pop(0)
        if sym not in watch or len(h) < 2:
            continue
        base = next((x for x in h if now_ms - x[0] <= sp["mins"] * 60000 + 20000), h[0])
        if base[1] <= 0:
            continue
        ch = (h[-1][1] / base[1] - 1) * 100
        if abs(ch) >= sp["pct"] and now_ms - COOL.get(sym, 0) > sp["cooldown"] * 60000:
            COOL[sym] = now_ms
            mins = max(1, round((now_ms - base[0]) / 60000))
            al = {"ts": now_ms, "script": "SPIKE", "sym": sym, "tf": f"{mins}m", "side": "long" if ch > 0 else "short", "price": h[-1][1], "chg": round(ch, 2)}
            msg = f"⚡ SPIKE {sym} {ch:+.2f}% in {mins} min | price {h[-1][1]}"
            al["sent"] = archive.tg_message(msg)["ok"]
            _push(al)
            out.append(al)
    return out


async def spike_loop(*_):
    await asyncio.sleep(30)
    while True:
        try:
            if cfg()["spike"].get("on"):
                await asyncio.get_running_loop().run_in_executor(None, spike_once)
        except Exception as e:
            LAST["error"] = ("spike: " + str(e))[:160]
        await asyncio.sleep(60)


async def loop(*_):
    await asyncio.gather(_scripts_loop(), spike_loop())


async def _scripts_loop():
    await asyncio.sleep(60)
    while True:
        try:
            await asyncio.get_running_loop().run_in_executor(None, run_once)
        except Exception:
            logging.exception("screener pass failed")
        await asyncio.sleep(max(1, float(cfg().get("every_min", 5))) * 60)
