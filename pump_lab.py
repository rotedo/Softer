"""Lab: real Binance Vision data -> what happened BEFORE pumps, and which settings would have caught them. Runs on GitHub (Actions) or anywhere:
    python pump_lab.py lab/job.json
job.json = {"name": "...", "mode": "profile" | "test", "settings": {pump_config changes}, "sweep": false, "coins": [{"sym": "VELVET", "from": "2026-11-12", "to": "2026-11-27"}]}
Writes lab_results/<name>.md (+ .json). Everything the sensors see is the past only; the pump labels are only the answer key."""
import datetime as dt, json, os, statistics as st, sys, time, traceback
import pump_config as cfg, pump_engine as E, pump_vision as VI

OUT = "lab_results"
STEP_MIN = 5
THRESH = {"volx": [2, 3, 5, 10], "vol3x": [2, 3, 5], "ret3": [1, 2, 3, 5], "ret12": [3, 5, 10], "rng": [3, 5, 8], "trx": [2, 3, 5], "oi12": [1, 2, 3, 5],
          "oi48": [2, 5, 10], "tb": [0.55, 0.6, 0.7], "tls": [1.2, 1.5, 2.0], "fneg": [0.01, 0.02, 0.05]}
WHAT = {"volx": "this candle's volume / average of previous 4h", "vol3x": "last 15 min volume / previous ~4h", "ret3": "% price change in 15 min",
        "ret12": "% price change in 1h", "rng": "candle size / average candle size (4h)", "trx": "number of trades / average (4h)", "oi12": "% open interest change in 1h",
        "oi48": "% open interest change in 4h", "tb": "share of taker BUY volume", "tls": "taker long/short volume ratio", "fneg": "negative funding (%, bigger = more negative)"}


def mean(x):
    return sum(x) / len(x) if x else 0.0


def utc(ms):
    return time.strftime("%m-%d %H:%M", time.gmtime(ms / 1000))


def signals(c):
    """for every candle i: sensors computed from candles up to i only"""
    n = len(c)
    S = {k: [None] * n for k in THRESH}
    q, tr = [x["q"] for x in c], [x["n"] for x in c]
    rg = [(x["h"] - x["l"]) / x["o"] if x["o"] > 0 else 0 for x in c]
    for i in range(50, n):
        b = mean(q[i - 48:i])
        S["volx"][i] = q[i] / b if b > 0 else None
        b3 = mean(q[i - 50:i - 2])
        S["vol3x"][i] = mean(q[i - 2:i + 1]) / b3 if b3 > 0 else None
        S["ret3"][i] = (c[i]["c"] / c[i - 3]["c"] - 1) * 100
        S["ret12"][i] = (c[i]["c"] / c[i - 12]["c"] - 1) * 100
        br = mean(rg[i - 48:i])
        S["rng"][i] = rg[i] / br if br > 0 else None
        bt = mean(tr[i - 48:i])
        S["trx"][i] = tr[i] / bt if bt > 0 else None
        if c[i]["oi"] and c[i - 12]["oi"]:
            S["oi12"][i] = (c[i]["oi"] / c[i - 12]["oi"] - 1) * 100
        if c[i]["oi"] and c[i - 48]["oi"]:
            S["oi48"][i] = (c[i]["oi"] / c[i - 48]["oi"] - 1) * 100
        S["tb"][i] = c[i]["tb"] / c[i]["v"] if c[i]["v"] > 0 else None
        S["tls"][i] = c[i].get("tls")
        S["fneg"][i] = -c[i]["fr"] * 100 if c[i]["fr"] is not None else None
    return S


def profile(coins):
    out, notes = [], []
    per = {(k, t): {"fired": 0, "already": [], "remain": [], "lead": [], "false": 0} for k, ts in THRESH.items() for t in ts}
    pumps_total, quiet_days = 0, 0.0
    for co in coins:
        c, nt = co["rows"], co["notes"]
        notes += nt
        sym = co["sym"]
        if len(c) < 120:
            out.append(f"### {sym}\nNOT ENOUGH DATA ({len(c)} candles). " + " ".join(nt) + "\n")
            continue
        pumps = [p for p in E.label_pumps(c) if p["start"] >= 60]
        S = signals(c)
        out.append(f"### {sym}: {len(c)} candles {utc(c[0]['t'])} to {utc(c[-1]['t'])} UTC; pumps found: {len(pumps)}")
        if not pumps:
            out.append(f"no pump matching the label (+{cfg.PUMP['pct']}% within {cfg.PUMP['window']} candles) in this window\n")
        busy = [False] * len(c)
        for p in pumps:
            for i in range(max(0, p["start"] - 288), min(len(c), p["peak"] + 144)):
                busy[i] = True
            lo = c[p["start"]]["l"]
            out.append(f"pump: bottom {utc(c[p['start']]['t'])}, top {utc(c[p['peak']]['t'])} UTC, +{p['gain']}% in {(p['peak'] - p['start']) * STEP_MIN // 60}h{(p['peak'] - p['start']) * STEP_MIN % 60:02d}m")
            pumps_total += 1
            for k, ts in THRESH.items():
                for t in ts:
                    rng = range(max(50, p["start"] - 288), p["peak"] + 1)
                    a = next((i for i in rng if S[k][i] is not None and S[k][i] >= t), None)
                    if a is None:
                        continue
                    r = per[(k, t)]
                    r["fired"] += 1
                    r["already"].append(max(0.0, (c[a]["c"] / lo - 1) * 100))
                    r["remain"].append((c[p["peak"]]["h"] / c[a]["c"] - 1) * 100)
                    r["lead"].append((p["peak"] - a) * STEP_MIN)
        mp = max(pumps, key=lambda p: p["gain"]) if pumps else None
        if mp:  # timeline around the biggest pump
            out.append("timeline of the biggest pump (rel = time from the bottom; price% = above the bottom):")
            out.append("  rel      price%  volx  vol3x  trx  oi1h%  oi4h%  tb    fund%")
            f = lambda v, w=5, d=1: "-".rjust(w) if v is None else f"{v:{w}.{d}f}"
            for off in (-288, -144, -72, -36, -12, -6, -3, 0, 3, 6, 12, 36):
                i = mp["start"] + off
                if 50 <= i < len(c):
                    lab = f"{off * STEP_MIN // 60:+d}h" if off % 12 == 0 else f"{off * STEP_MIN:+d}m"
                    fr = None if c[i]["fr"] is None else c[i]["fr"] * 100
                    out.append(f"  {lab:>6} {f((c[i]['c'] / c[mp['start']]['l'] - 1) * 100, 7)} {f(S['volx'][i])} {f(S['vol3x'][i])} {f(S['trx'][i])} {f(S['oi12'][i], 6)} {f(S['oi48'][i], 6)} {f(S['tb'][i], 5, 2)} {f(fr, 6, 3)}")
        # false-fire episodes outside every pump zone
        for k, ts in THRESH.items():
            for t in ts:
                last = -999
                for i in range(50, len(c)):
                    if not busy[i] and S[k][i] is not None and S[k][i] >= t and i - last > 24:
                        per[(k, t)]["false"] += 1
                        last = i
        quiet_days += sum(1 for i in range(50, len(c)) if not busy[i]) / 288
        out.append("")
    lines = [f"SIGNALS BEFORE THE MOVE on {pumps_total} pump(s). fired = first time the signal reached the level between 1 day before the bottom and the top.",
             "already% = how much price had already risen from the bottom when it fired (small = early); left% = what was still to come to the top; false/day = firings in quiet times (no pump near), per coin-day.",
             "signal   level | fired   already%  left%  lead(min) | false/day  | meaning"]
    rows = []
    for (k, t), r in per.items():
        if not r["fired"]:
            continue
        rows.append((-r["fired"], st.median(r["already"]), k, t, r))
    for _, _, k, t, r in sorted(rows, key=lambda x: (x[0], x[1])):
        fd = r["false"] / quiet_days if quiet_days else 0
        lines.append(f"{k:7} {t:6g} | {r['fired']:3}/{pumps_total:<3} {st.median(r['already']):8.1f} {st.median(r['remain']):6.1f} {st.median(r['lead']):9.0f} | {fd:8.2f}   | {WHAT[k]}")
    return "\n".join(lines + [""] + out), notes


def test(coins, sweep):
    sets = [co for co in coins if len(co["rows"]) >= E.WARMUP + 50]
    out = []
    for co in coins:
        if co not in sets:
            out.append(f"{co['sym']}: NOT ENOUGH DATA ({len(co['rows'])} candles) {' '.join(co['notes'])}")
    results = [E.run_coin(co["rows"]) for co in sets]
    rows = E.aggregate(results)
    out.append(E.table(rows, f"TEST on {len(sets)} coins; pump = +{cfg.PUMP['pct']}% in {cfg.PUMP['window'] * STEP_MIN} min; hit = +{cfg.EVAL['hit_pct']}% in {cfg.EVAL['horizon'] * STEP_MIN // 60}h; need {cfg.MIN_STRATEGIES}+ sensors for 'combined'"))
    out.append("\nPER COIN (combined view; 'all' = any single sensor):")
    for co, r in zip(sets, results):
        c = co["rows"]
        for pi, p in enumerate(r["pumps"]):
            cm = r["views"]["combined"]["caught"][pi]
            anyv = [(v, d["caught"][pi]) for v, d in r["views"].items() if v != "combined" and d["caught"][pi]]
            first = min(anyv, key=lambda x: x[1]["alert"]) if anyv else None
            txt = f"combined at {utc(c[cm['alert']]['t'])} (already +{cm['already_pct']}%, lead {cm['lead_min']} min)" if cm else "combined: MISSED"
            ft = f"; earliest single: {first[0]} at {utc(c[first[1]['alert']]['t'])} (already +{first[1]['already_pct']}%)" if first else "; no single sensor fired"
            out.append(f"{co['sym']:8} pump {utc(c[p['start']]['t'])}->{utc(c[p['peak']]['t'])} +{p['gain']}%: {txt}{ft}")
        if not r["pumps"]:
            out.append(f"{co['sym']:8} no pump found by the label in this window")
    if sweep and sets:
        out.append("\n" + E.sweep_text(E.sweep([co["rows"] for co in sets], progress=lambda m: None), len(sets)))
    return "\n".join(out)


def main(path):
    job = json.load(open(path))
    name = job.get("name", "run")
    os.makedirs(OUT, exist_ok=True)
    t0 = time.time()
    try:
        err = cfg.apply(job.get("settings", {}))
        if err:
            raise ValueError("bad settings: " + "; ".join(err))
        coins = []
        for co in job["coins"]:
            rows, notes = VI.fetch(co["sym"] + "USDT", dt.date.fromisoformat(co["from"]), dt.date.fromisoformat(co["to"]))
            coins.append({"sym": co["sym"], "rows": rows, "notes": notes})
        head = [f"# {name}  ({job.get('mode')})", f"settings changed for this run: {json.dumps(job.get('settings', {}))}",
                "data: " + ", ".join(f"{c['sym']}={len(c['rows'])}" for c in coins)]
        notes = [n for c in coins for n in c["notes"]]
        if job.get("mode") == "profile":
            body, _ = profile(coins)
        else:
            body = test(coins, job.get("sweep"))
        text = "\n".join(head + (["data notes:"] + notes if notes else []) + ["", "```", body, "```", f"(took {time.time() - t0:.0f}s; real Binance Vision data; sensors see only the past)"])
    except Exception:
        text = f"# {name}  FAILED\n```\n{traceback.format_exc()}\n```"
    open(os.path.join(OUT, name + ".md"), "w").write(text)
    print(text[:3000])


if __name__ == "__main__":
    main(sys.argv[1])
