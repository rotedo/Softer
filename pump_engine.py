"""Candle-by-candle backtest. At candle i every sensor receives a COPY of the candles ending at i (nothing after i exists for it).
Views = each sensor alone + 'combined' (at least MIN_STRATEGIES sensors agree at the same candle).
Answers: of the real pumps, how many did we catch (and early)? of the alerts, how many were followed by +hit% (the rest are false alerts)?"""
import pump_config as cfg
import pump_strategies as S

WARMUP = 60  # candles before the first judged candle
STEP_MIN = 5  # candle size in minutes (the backtest works on 5m candles)


def label_pumps(c):
    """real pumps in the data: price rises PUMP.pct % within PUMP.window candles. start = the bottom of the move, peak = where the run ends.
    -> [{start, peak, gain}] (indexes into c). Uses the whole history on purpose: this is the ANSWER KEY, never given to a sensor."""
    p, out, i, n = cfg.PUMP, [], 0, len(c)
    w = int(p["window"])
    while i < n - 1:
        seg = c[i + 1:i + 1 + w]
        if seg and max(x["h"] for x in seg) >= c[i]["l"] * (1 + p["pct"] / 100):
            j = max(range(i + 1, i + 1 + len(seg)), key=lambda k: c[k]["h"])
            while True:  # the run goes on while new highs keep coming within the window
                nxt = c[j + 1:j + 1 + w]
                if nxt and max(x["h"] for x in nxt) > c[j]["h"]:
                    j = max(range(j + 1, j + 1 + len(nxt)), key=lambda k: c[k]["h"])
                else:
                    break
            s = min(range(i, j + 1), key=lambda k: c[k]["l"])
            out.append({"start": s, "peak": j, "gain": round((c[j]["h"] / c[s]["l"] - 1) * 100, 1)})
            i = j + 1
        else:
            i += 1
    return out


def alerts_for(c):
    """-> {view: [candle index]} using only the past at every step"""
    lb, cool = int(cfg.EVAL["lookback"]), int(cfg.EVAL["cooldown"])
    out, last = {}, {}
    for i in range(WARMUP, len(c)):
        win = c[max(0, i + 1 - lb):i + 1]  # a copy that ends exactly at candle i
        res = S.run_all(win)
        ok = [k for k, (b, _) in res.items() if b]
        mine = ["my_" + k for k, (b, _) in S.run_custom(win).items() if b]  # your own setups: own views, not part of 'combined'
        views = ok + mine + (["combined"] if len(ok) >= cfg.MIN_STRATEGIES else [])
        for v in views:
            if i - last.get(v, -10 ** 9) > cool:
                out.setdefault(v, []).append(i)
                last[v] = i
    return out


def judge(c, i):
    """what happened after an alert at candle i: best / worst move, hit or not, minutes until the hit"""
    h = int(cfg.EVAL["horizon"])
    fut = c[i + 1:i + 1 + h]
    if not fut:
        return None
    base = c[i]["c"]
    best = (max(x["h"] for x in fut) / base - 1) * 100
    worst = (min(x["l"] for x in fut) / base - 1) * 100
    hit = best >= cfg.EVAL["hit_pct"]
    t_hit = None
    if hit:
        t_hit = next((k + 1 for k, x in enumerate(fut) if x["h"] >= base * (1 + cfg.EVAL["hit_pct"] / 100)), None)
    return {"i": i, "hit": hit, "best": round(best, 1), "worst": round(worst, 1), "min_to_hit": t_hit * STEP_MIN if t_hit else None}


def run_coin(c):
    """one coin -> {n, pumps, views: {view: {alerts: [judged], caught: [per pump: None or {...}]}}}"""
    pumps = [p for p in label_pumps(c) if p["start"] >= WARMUP]
    al, views = alerts_for(c), {}
    names = [k for k, v in cfg.STRATEGY_CONFIG.items() if v.get("enabled")] + ["my_" + k for k in S.CUSTOM] + ["combined"]
    for v in names:
        idx = al.get(v, [])
        judged = [j for j in (judge(c, i) for i in idx) if j]
        caught = []
        for p in pumps:
            a = next((i for i in idx if p["start"] - 6 <= i <= p["peak"]), None)  # alert from just before the move starts until its top
            if a is None:
                caught.append(None)
                continue
            already = (c[a]["c"] / c[p["start"]]["l"] - 1) * 100
            caught.append({"alert": a, "lead_min": (p["peak"] - a) * STEP_MIN, "already_pct": round(already, 1), "early": already <= p["gain"] / 2})
        views[v] = {"alerts": judged, "caught": caught}
    return {"n": len(c), "pumps": pumps, "views": views}


def _pct(a, b):
    return round(100 * a / b, 1) if b else None


def _avg(xs):
    return round(sum(xs) / len(xs), 1) if xs else None


def aggregate(results):
    """many coins -> one row per view"""
    rows = []
    names = list(results[0]["views"]) if results else []
    for v in names:
        al = [a for r in results for a in r["views"][v]["alerts"]]
        ca = [x for r in results for x in r["views"][v]["caught"]]
        got = [x for x in ca if x]
        days = sum(r["n"] for r in results) * STEP_MIN / 1440
        rows.append({"view": v, "alerts": len(al), "hits": sum(1 for a in al if a["hit"]), "hit_pct": _pct(sum(1 for a in al if a["hit"]), len(al)),
                     "pumps": len(ca), "caught": len(got), "catch_pct": _pct(len(got), len(ca)), "early": sum(1 for x in got if x["early"]),
                     "avg_lead_min": _avg([x["lead_min"] for x in got]), "avg_already": _avg([x["already_pct"] for x in got]), "avg_best": _avg([a["best"] for a in al]), "avg_worst": _avg([a["worst"] for a in al]),
                     "alerts_per_coin_day": round(len(al) / days, 2) if days else None})
    return rows


def table(rows, title=""):
    f = lambda x: "-" if x is None else x
    lines = [title, "view            alerts hit% | pumps caught catch% early | lead(min) best% worst% | alerts/coin-day"]
    for r in rows:
        lines.append(f"{r['view'][:15]:15} {r['alerts']:6} {str(f(r['hit_pct'])):>5} | {r['pumps']:5} {r['caught']:6} {str(f(r['catch_pct'])):>6} {r['early']:5} | "
                     f"{str(f(r['avg_lead_min'])):>9} {str(f(r['avg_best'])):>5} {str(f(r['avg_worst'])):>6} | {f(r['alerts_per_coin_day'])}")
    lines.append("catch% = real pumps we alerted on in time. hit% = alerts followed by the hit move; the rest are false alerts.")
    return "\n".join(lines)


# ---------------- settings sweep: which numbers would have caught the move, and what do they cost in false alerts ----------------
SWEEP_GRID = [("STRATEGY_CONFIG.volume_spike.volume_multiplier", [2, 3, 4, 5, 8]), ("STRATEGY_CONFIG.price_momentum.min_return_pct", [1, 2, 3, 5]),
              ("STRATEGY_CONFIG.price_momentum.bars", [2, 3, 4]), ("STRATEGY_CONFIG.price_momentum.breakout_candles", [12, 24, 48]),
              ("STRATEGY_CONFIG.open_interest.oi_change_percent", [2, 3, 5, 8]), ("MIN_STRATEGIES", [1, 2, 3])]


def _nest(path, v):
    d = v
    for k in reversed(path.split(".")):
        d = {k: d}
    return d


def sweep(sets, progress=print):
    """Change ONE setting at a time around the current numbers and re-run the whole candle-by-candle test on every coin in `sets`.
    Returns rows (view 'combined'). The current numbers are always restored. Nothing here knows the future."""
    base, rows = cfg.snapshot(), []
    try:
        for path, vals in SWEEP_GRID:
            cur = base
            for k in path.split("."):
                cur = cur[k]
            for v in vals:
                cfg.apply(_nest(path, v))
                row = next(r for r in aggregate([run_coin(c) for c in sets]) if r["view"] == "combined")
                row.update(param=path.split(".")[-1], value=v, current=(v == cur))
                rows.append(row)
            cfg.apply(_nest(path, cur))
            progress(f"{path.split('.')[-1]} done")
    finally:
        cfg.apply(base)
    return rows


def sweep_text(rows, ncoins):
    f = lambda x: "-" if x is None else x
    out = [f"SETTINGS SWEEP on {ncoins} coin(s). One setting changed at a time (* = your current number). 'combined' = enough sensors agree.",
           "setting              value | caught early | lead(min) already% | alerts hit% alerts/day"]
    last = None
    for r in rows:
        if r["param"] != last:
            out.append("")
            last = r["param"]
        out.append(f"{r['param'][:20]:20} {str(r['value']) + ('*' if r['current'] else ''):>6} | {r['caught']}/{r['pumps']} {r['early']:>6} | {str(f(r['avg_lead_min'])):>8} {str(f(r['avg_already'])):>8} | "
                   f"{r['alerts']:6} {str(f(r['hit_pct'])):>5} {f(r['alerts_per_coin_day'])}")
    out += ["", "How to read: lead = minutes between the alert and the top; already% = how much the price had already risen when the alert came (small = early).",
            "Do NOT pick the single best row (that is overfitting). Prefer a RANGE of neighbouring values that all catch the move with few alerts per day, then check the same numbers on Group B."]
    return "\n".join(out)
