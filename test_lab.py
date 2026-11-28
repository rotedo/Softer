"""Test of pump_vision + pump_lab on FAKE Binance Vision files (no internet). Run: python test_lab.py"""
import datetime as dt, io, json, os, random, sys, tempfile, zipfile, time
os.environ.update(DB_PATH=os.path.join(tempfile.mkdtemp(), "o.db"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pump_vision as VI, pump_lab as LAB, pump_config as cfg

D0 = dt.date(2026, 11, 10)
PUMP_AT = dt.datetime(2026, 11, 14, 12, 0, tzinfo=dt.timezone.utc)
T0 = int(dt.datetime(2026, 11, 1, tzinfo=dt.timezone.utc).timestamp() * 1000)


def series(sym):
    rnd, p, out = random.Random(sym), 100.0, []
    k0 = int((PUMP_AT.timestamp() * 1000 - T0) // 300_000) if sym == "AAAUSDT" else None
    for i in range(20 * 288):
        o = p
        v = 1000 * (1 + rnd.random() * 0.3)
        if k0 is not None and k0 <= i < k0 + 10:
            p *= 1.07; v *= 10
        else:
            p *= 1 + rnd.uniform(-0.003, 0.003)
        out.append((T0 + i * 300_000, o, max(o, p) * 1.001, min(o, p) * 0.999, p, v, v * p, 40 + int(v / 50)))
    return out


def zipped(name, text):
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        z.writestr(name, text)
    return b.getvalue()


def fake_get(url):
    parts = url.split("/")
    sym = parts[-3] if "/klines/" in url else parts[-2]
    if sym not in ("AAAUSDT", "BBBUSDT"):
        return None
    f = parts[-1]
    if "/klines/" in url:
        day = f.rsplit("-", 3)[1:]
        d = dt.date(int(day[0]), int(day[1]), int(day[2].split(".")[0]))
        lo = int(dt.datetime(d.year, d.month, d.day, tzinfo=dt.timezone.utc).timestamp() * 1000)
        rows = [r for r in series(sym) if lo <= r[0] < lo + 86_400_000]
        if not rows:
            return None
        txt = "open_time,open,high,low,close,volume,close_time,quote_volume,count,taker_buy_volume,taker_buy_quote_volume,ignore\n"
        txt += "\n".join(f"{t},{o},{h},{l},{c},{v},{t + 299999},{q},{n},{v * 0.6},{q * 0.6},0" for t, o, h, l, c, v, q, n in rows)
        return zipped(f.replace(".zip", ".csv"), txt)
    if "/metrics/" in url:
        d = f.replace(".zip", "").split("metrics-")[1]
        lo = int(dt.datetime.strptime(d, "%Y-%m-%d").replace(tzinfo=dt.timezone.utc).timestamp() * 1000)
        k0 = (PUMP_AT.timestamp() * 1000 - T0) // 300_000
        txt = "create_time,symbol,sum_open_interest,sum_open_interest_value,count_toptrader_long_short_ratio,sum_toptrader_long_short_ratio,count_long_short_ratio,sum_taker_long_short_vol_ratio\n"
        for t in range(lo, lo + 86_400_000, 300_000):
            i = (t - T0) // 300_000
            oi = 1e6 * (1 + (0.04 * (i - k0 + 6) if sym == "AAAUSDT" and k0 - 6 <= i < k0 + 10 else 0.5 if sym == "AAAUSDT" and i >= k0 + 10 else 0))
            txt += f"{time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(t / 1000))},{sym},1,{oi},1,1,1,1.3\n"
        return zipped("m.csv", txt)
    if "/fundingRate/" in url:
        return zipped("f.csv", "calc_time,funding_interval_hours,last_funding_rate\n" + "\n".join(f"{T0 + h * 3_600_000},8,0.0001" for h in range(0, 480, 8)))
    return None


VI.GET = fake_get
rows, notes = VI.fetch("AAAUSDT", dt.date(2026, 11, 10), dt.date(2026, 11, 16))
assert len(rows) == 7 * 288 and rows[0]["oi"] is not None and rows[500]["fr"] == 0.0001 and rows[500]["tls"] == 1.3 and not notes, (len(rows), notes)
r2, n2 = VI.fetch("ZZZUSDT", dt.date(2026, 11, 10), dt.date(2026, 11, 12))
assert r2 == [] and "no candle file" in n2[0]
print("OK   vision loader: candles, open interest, taker ratio, funding; missing coin reported")

tmp = tempfile.mkdtemp()
os.chdir(tmp)
job = {"name": "t_profile", "mode": "profile", "settings": {"PUMP": {"pct": 30, "window": 288}},
       "coins": [{"sym": "AAA", "from": "2026-11-10", "to": "2026-11-17"}, {"sym": "BBB", "from": "2026-11-10", "to": "2026-11-17"}, {"sym": "ZZZ", "from": "2026-11-10", "to": "2026-11-17"}]}
json.dump(job, open("job.json", "w"))
LAB.main("job.json")
txt = open("lab_results/t_profile.md").read()
assert "FAILED" not in txt and "pumps found: 1" in txt and "volx" in txt and "ZZZ" in txt and "NOT ENOUGH DATA" in txt, txt[:1500]
assert "SIGNALS BEFORE THE MOVE on 1 pump" in txt
cfg.reset()
job = {"name": "t_test", "mode": "test", "settings": {"STRATEGY_CONFIG": {"trades_spike": {"enabled": True}}}, "sweep": False,
       "coins": [{"sym": "AAA", "from": "2026-11-10", "to": "2026-11-17"}, {"sym": "BBB", "from": "2026-11-10", "to": "2026-11-17"}]}
json.dump(job, open("job2.json", "w"))
LAB.main("job2.json")
t2 = open("lab_results/t_test.md").read()
assert "FAILED" not in t2 and "combined at" in t2 and "trades_spike" in t2, t2[:1500]
print(t2[:2500])
cfg.reset()
job["settings"] = {"EVAL": {"horizon": "abc"}}
json.dump(job, open("job3.json", "w"))
LAB.main("job3.json")
assert "bad settings" in open("lab_results/t_test.md").read()
print("OK   lab: profile + test + bad settings reported")
cfg.reset()
job = {"name": "t_universe", "mode": "universe", "end": "2026-11-17", "days": 6, "syms": ["AAAUSDT", "BBBUSDT", "BTCUSDT"], "settings": {"PUMP": {"pct": 30, "window": 288}},
       "candidates": [{"tag": "no filters", "settings": {"FILTER": {"max_run_pct": 0, "min_candle_usd": 0, "max_wick_ratio": 1}}}, {"tag": "defaults", "settings": {}, "detail": True},
                      {"tag": "strict", "settings": {"MIN_STRATEGIES": 3, "FILTER": {"confirm_candles": 2}}}]}
json.dump(job, open("job4.json", "w"))
LAB.main("job4.json")
u = open("lab_results/t_universe.md").read()
assert "FAILED" not in u and "no filters" in u and "strict" in u and "PUMPS for candidate 'defaults'" in u and "caught AAA" in u and "coins with data: 2" in u, u[:2500]
print(u[:1800])
print("OK   universe mode")
print("ALL LAB TESTS PASSED (fake data only)")
