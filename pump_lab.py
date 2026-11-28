"""Lab: real Binance Vision data -> what happened BEFORE pumps, and which settings would have caught them. Runs on GitHub (Actions) or anywhere:
    python pump_lab.py lab/job.json
job.json = {"name": "...", "mode": "profile" | "test", "settings": {pump_config changes}, "sweep": false, "coins": [{"sym": "VELVET", "from": "2026-11-12", "to": "2026-11-27"}]}
Writes lab_results/<name>.md (+ .json). Everything the sensors see is the past only; the pump labels are only the answer key."""
import datetime as dt, json, os, statistics as st, sys, time, traceback
from concurrent.futures import ThreadPoolExecutor
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


MAJORS = {"BTC", "ETH", "BNB", "XRP", "SOL", "USDC", "BUSD", "TUSD", "FDUSD"}


def dcx_bases():
    """coin names listed on CoinDCX futures (None if CoinDCX cannot be reached from here)"""
    try:
        d = VI.GET("https://api.coindcx.com/exchange/v1/derivatives/futures/data/active_instruments?margin_currency_short_name[]=USDT")
        return {(p if isinstance(p, str) else p.get("pair", "")).split("-", 1)[-1].rsplit("_", 1)[0] for p in json.loads(d)} - {""} if d else None
    except Exception:
        return None


def eval_candidate(coins, tag):
    """alerts on every coin with the CURRENT settings. -> (summary dict, sample lines, pump lines)"""
    n = hit = hit24 = pumps = caught = early = 0
    days = 0.0
    samples, plines = [], []
    for sym, c in coins.items():
        al = E.alerts_for(c).get("combined", [])
        days += len(c) / 288
        for i in al:
            j = E.judge(c, i)
            if not j:
                continue
            n += 1
            hit += j["hit"]
            b24 = (max(x["h"] for x in c[i + 1:i + 289]) / c[i]["c"] - 1) * 100
            hit24 += b24 >= 20
            samples.append((sym, utc(c[i]["t"]), j["best"], j["worst"], round(b24, 1)))
        for p in (p for p in E.label_pumps(c) if p["start"] >= E.WARMUP):
            pumps += 1
            a = next((i for i in al if p["start"] - 6 <= i <= p["peak"]), None)
            if a is None:
                plines.append(f"MISSED {sym} bottom {utc(c[p['start']]['t'])} +{p['gain']}%")
                continue
            caught += 1
            already = (c[a]["c"] / c[p["start"]]["l"] - 1) * 100
            early += already <= 10
            plines.append(f"caught {sym} bottom {utc(c[p['start']]['t'])} +{p['gain']}% alert {utc(c[a]['t'])} already +{already:.0f}%")
    d = max(days / max(1, len(coins)), 1e-9)  # days per coin
    return {"tag": tag, "alerts": n, "alerts_day": round(n / d, 1), "right10": round(100 * hit / n, 1) if n else None, "right20_24h": round(100 * hit24 / n, 1) if n else None,
            "pumps": pumps, "pumps_day": round(pumps / d, 1), "caught": caught, "early": early}, samples, plines


def universe(job):
    end = dt.date.fromisoformat(job["end"]) if job.get("end") else dt.datetime.now(dt.timezone.utc).date() - dt.timedelta(days=2)
    start = end - dt.timedelta(days=int(job.get("days", 5)) - 1)
    syms = job.get("syms") or VI.list_symbols()
    lines = [f"universe: {len(syms)} USDT perps on Binance Vision; days {start} to {end}"]
    keep = [s for s in syms if s[:-4] not in MAJORS]
    bases = dcx_bases() if job.get("dcx") else None
    if bases:
        plain = lambda b: b[7:] if b.startswith("1000000") else b[4:] if b.startswith("1000") else b
        keep = [s for s in keep if s[:-4] in bases or plain(s[:-4]) in bases]
        lines.append(f"restricted to coins also listed on CoinDCX futures ({len(bases)} there): {len(keep)} coins")
    else:
        lines.append("CoinDCX list not used (not requested or not reachable): all non-major Binance coins")
    coins, notes = {}, 0

    def one(s):
        rows, _ = VI.fetch(s, start, end)
        return s, rows
    with ThreadPoolExecutor(max_workers=6) as ex:
        for s, rows in ex.map(one, keep):
            if len(rows) > 400:
                coins[s] = rows
    lines.append(f"coins with data: {len(coins)} (download {time.time() - T0:.0f}s)")
    res, first = [], None
    for cand in job["candidates"]:
        cfg.reset()
        err = cfg.apply(job.get("settings", {})) or cfg.apply(cand.get("settings", {}))  # job-wide settings (e.g. the pump label) first, then this candidate's
        if err:
            raise ValueError(cand["tag"] + ": " + "; ".join(err))
        r, samples, plines = eval_candidate(coins, cand["tag"])
        res.append(r)
        if first is None or cand.get("detail"):
            first = (cand["tag"], samples, plines)
        lines.append(f"done {cand['tag']} ({time.time() - T0:.0f}s)")
    out = lines + ["", "candidate                     alerts/day  right(+10% in 6h)  right(+20% in 24h) | pumps/day  caught  early(<=10% up)"]
    for r in res:
        out.append(f"{r['tag'][:28]:28} {r['alerts_day']:10} {str(r['right10']):>17} {str(r['right20_24h']):>19} | {r['pumps_day']:9} {r['caught']:>3}/{r['pumps']:<4} {r['early']}")
    out.append("alerts/day = over ALL coins together. right = share of alerts followed by that rise. pumps = real moves (label) found in the same data.")
    tag, samples, plines = first
    out += ["", f"PUMPS for candidate '{tag}':"] + plines[:80] + ["", f"SAMPLE ALERTS for '{tag}' (coin, time, best%, worst%, best in 24h%):"] + [str(x) for x in samples[:40]]
    return "\n".join(out)


T0 = time.time()


def dcxcheck(job):
    """does CoinDCX give OLD 5m futures candles? ask for ranges far back and report what comes back"""
    out = ["CoinDCX futures 5m candles: how far back does the public API go?"]
    now = int(time.time())
    for pair in job.get("pairs", ["B-BTC_USDT", "B-BULLA_USDT", "B-ACE_USDT"]):
        for days in job.get("back", [1, 7, 30, 90, 180, 365]):
            t1 = now - (days - 1) * 86400
            t0_ = t1 - 86400  # one day window that far back
            try:
                d = json.loads(VI.GET(f"https://public.coindcx.com/market_data/candlesticks?pair={pair}&from={t0_}&to={t1}&resolution=5&pcode=f"))
                rows = d["data"] if isinstance(d, dict) else d
                tt = sorted(int(k["time"]) for k in rows)
                tt = [x // 1000 if x > 1e11 else x for x in tt]
                out.append(f"{pair} {days:4}d back: {len(rows):4} candles" + (f", {time.strftime('%Y-%m-%d %H:%M', time.gmtime(tt[0]))} to {time.strftime('%Y-%m-%d %H:%M', time.gmtime(tt[-1]))} UTC" if rows else ""))
            except Exception as e:
                out.append(f"{pair} {days:4}d back: FAILED {type(e).__name__}: {str(e)[:100]}")
    return "\n".join(out)


def main(path):
    job = json.load(open(path))
    if isinstance(job, list):  # several jobs in one file, run one after the other
        for j in job:
            json.dump(j, open("/tmp/_job.json", "w"))
            main("/tmp/_job.json")
        return
    name = job.get("name", "run")
    os.makedirs(OUT, exist_ok=True)
    t0 = time.time()
    try:
        err = cfg.apply(job.get("settings", {}))
        if err:
            raise ValueError("bad settings: " + "; ".join(err))
        if job.get("mode") == "dcxcheck":
            text = f"# {name}\n```\n{dcxcheck(job)}\n```"
            open(os.path.join(OUT, name + ".md"), "w").write(text)
            print(text[:3000])
            return
        if job.get("mode") == "universe":
            text = f"# {name}  (universe)\n```\n{universe(job)}\n```\n(took {time.time() - t0:.0f}s; real Binance Vision data)"
            open(os.path.join(OUT, name + ".md"), "w").write(text)
            print(text[:3000])
            return
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
