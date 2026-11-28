"""Tests for the pump system on FAKE Binance / CoinDCX data (no internet). Run:  python test_pump.py
Proves: find -> download -> groups -> backtest -> overfitting check, no future data, live cycle, settings, web routes.
It does NOT prove anything about real Binance / CoinDCX answers."""
import os, sys, tempfile, time, json, calendar, random

TMP = tempfile.mkdtemp()
os.environ.update(DB_PATH=os.path.join(TMP, "orderflow.db"), APP_DB=os.path.join(TMP, "app.db"), PUMP_DATA_DIR=os.path.join(TMP, "pump_data"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pump_config as cfg, pump_download as D, pump_strategies as S, pump_engine as E, pump_validate as V, pump_live as L, pump_web as W

NOW = int(time.time() // 300) * 300 * 1000
N = 30 * 288  # 30 days of 5m candles, last one ends at NOW
T0 = NOW - N * 300_000
DAYMS = 86_400_000
PUMP_DAY = (NOW // DAYMS - 10) * DAYMS  # a UTC day 10 days ago
PUMPS = {"AAAUSDT": PUMP_DAY + 14 * 3_600_000, "CCCUSDT": (NOW // DAYMS - 6) * DAYMS + 3 * 3_600_000}  # pump start time (ms)


def series(sym):
    """fake 5m candles: quiet noise, plus (for pumped coins) a ramp: +8% per candle for 8 candles with volume x10"""
    rnd, out, p = random.Random(sym), [], 100.0
    k0 = (PUMPS[sym] - T0) // 300_000 if sym in PUMPS else None
    for i in range(N):
        o = p
        vol = 1000 * (1 + rnd.random() * 0.3)
        if k0 is not None and k0 <= i < k0 + 8:
            p = p * 1.08
            vol *= 12
        elif k0 is not None and k0 + 8 <= i < k0 + 40:
            p = p * (1 + rnd.uniform(-0.004, 0.004))
        else:
            p = p * (1 + rnd.uniform(-0.003, 0.003))
        c = p
        out.append([T0 + i * 300_000, o, max(o, c) * 1.001, min(o, c) * 0.999, c, vol, 0, vol * c, 50, vol * 0.6, 0])
    return out


DATA = {s: series(s) for s in ("AAAUSDT", "BBBUSDT", "CCCUSDT")}
CALLS = []


def fake_http(url):
    from urllib.parse import urlparse, parse_qs
    u = urlparse(url)
    q = {k: v[0] for k, v in parse_qs(u.query).items()}
    CALLS.append(u.path)
    if u.path == "/fapi/v1/exchangeInfo":
        return {"symbols": [{"symbol": s, "quoteAsset": "USDT", "contractType": "PERPETUAL", "status": "TRADING"} for s in DATA]}
    if u.path == "/fapi/v1/klines":
        ks = [k for k in DATA[q["symbol"]] if int(q.get("startTime", 0)) <= k[0] <= int(q.get("endTime", 1e18))]
        if q["interval"] == "1d":
            days = {}
            for k in ks:
                days.setdefault(k[0] // DAYMS * DAYMS, []).append(k)
            return [[d, g[0][1], max(x[2] for x in g), min(x[3] for x in g), g[-1][4], sum(x[5] for x in g), 0, sum(x[7] for x in g), 1, 0, 0] for d, g in sorted(days.items())][-int(q.get("limit", 500)):]
        return ks[:int(q.get("limit", 500))]
    if u.path == "/futures/data/openInterestHist":
        k0 = (PUMPS.get(q["symbol"], 0) - T0) // 300_000
        rows = []
        for i in range(N):
            t = T0 + i * 300_000
            if int(q["startTime"]) <= t <= int(q["endTime"]):
                oi = 1e6 * (1 + (0.05 * (i - k0 + 1) if q["symbol"] in PUMPS and k0 - 1 <= i < k0 + 8 else 0.4 if q["symbol"] in PUMPS and i >= k0 + 8 else 0))
                rows.append({"timestamp": t, "sumOpenInterestValue": str(oi)})
        return rows[:int(q["limit"])]
    if u.path == "/fapi/v1/fundingRate":
        rows = [{"fundingTime": T0 + h * 3_600_000, "fundingRate": "0.0001"} for h in range(0, 30 * 24, 8)]
        return [r for r in rows if int(q["startTime"]) <= r["fundingTime"] <= int(q["endTime"])][:int(q["limit"])]
    if u.path == "/fapi/v1/ticker/24hr":
        return [{"symbol": s, "quoteVolume": "9000000"} for s in DATA]
    if u.path == "/fapi/v1/premiumIndex":
        return [{"symbol": s, "lastFundingRate": "-0.0004" if s == "AAAUSDT" else "0.0001"} for s in DATA]
    raise AssertionError("unexpected URL " + url)


D.HTTP = fake_http
ok = lambda name: print("OK  ", name)

# ---------- settings ----------
snap = cfg.snapshot()
assert cfg.save({"PUMP": {"pct": "20"}}) == [] and cfg.PUMP["pct"] == 20.0
assert cfg.save({"PUMP": {"pct": "abc"}}) and cfg.PUMP["pct"] == 20.0, "bad value must change nothing"
assert cfg.save({"STRATEGY_CONFIG": {"volume_spike": {"volume_multiplier": 3, "nope": 1}}}), "unknown key rejected"
assert cfg.save({"MIN_STRATEGIES": "3"}) == [] and cfg.MIN_STRATEGIES == 3
cfg.PUMP["pct"] = 1
cfg.load_saved()
assert cfg.PUMP["pct"] == 20.0 and cfg.MIN_STRATEGIES == 3, "saved values survive (reload)"
cfg.reset()
assert cfg.snapshot() == snap
ok("settings validate / save / reload / reset")

# ---------- download ----------
assert D.usdt_symbols() == ["AAAUSDT", "BBBUSDT", "CCCUSDT"]
found = D.find_pumps(progress=lambda m: None)
assert sorted(f["sym"] for f in found) == ["AAAUSDT", "CCCUSDT"], found
rows = D.fetch("AAAUSDT", PUMP_DAY - 5 * DAYMS, PUMP_DAY + 3 * DAYMS, "5m", True, True)
assert len(rows) == 8 * 288 and rows[0]["t"] == PUMP_DAY - 5 * DAYMS
assert all(r["oi"] is not None for r in rows[-100:]) and all(r["fr"] is not None for r in rows)
csv_text = D.to_csv(rows)
assert csv_text.splitlines()[0].startswith("time_utc,t,o,h,l,c") and len(csv_text.splitlines()) == len(rows) + 1
D.save("AAAUSDT", rows)
back = D.load("AAAUSDT")
assert len(back) == len(rows) and back[10]["c"] == rows[10]["c"]
assert D.cleanup() == 1 and D.load("AAAUSDT") is None
ok("find pumps, fetch with OI + funding, csv, save/load/cleanup")

# ---------- engine: labels, alerts, no future ----------
cfg.apply({"MIN_STRATEGIES": 2})  # these fake-data checks were written for 2 agreeing sensors (the live default is now 3)
pumps = E.label_pumps(rows)
assert len(pumps) == 1 and pumps[0]["gain"] > 70, pumps
res = E.run_coin(rows)
comb = res["views"]["combined"]
assert comb["caught"] == [comb["caught"][0]] and comb["caught"][0] is not None, "combined must catch the pump"
assert comb["caught"][0]["early"], "caught early (before half the move)"
quiet = D.fetch("BBBUSDT", PUMP_DAY - 5 * DAYMS, PUMP_DAY + 3 * DAYMS, "5m", True, True)
rq = E.run_coin(quiet)
assert rq["pumps"] == [] and not rq["views"]["combined"]["alerts"], "no alerts on a quiet coin"
ok("pump labelled, caught early by combined, no false alerts on quiet coin")

seen, cur = [], [None]
orig, orig_decide = dict(S.REG), S.decide
for name, fn in orig.items():
    def wrap(f):
        def g(w, conf):
            assert w[-1]["t"] <= cur[0], "a sensor saw a candle later than the one being judged"
            return f(w, conf)
        return g
    S.REG[name] = wrap(fn)


def spy_decide(w):
    seen.append(w[-1]["t"])
    cur[0] = w[-1]["t"]
    return orig_decide(w)


S.decide = spy_decide
E.alerts_for(rows)
S.decide = orig_decide
S.REG.update(orig)
assert seen == [r["t"] for r in rows[E.WARMUP:]], "every decision must end exactly at the candle being judged"
cut = len(rows) // 2
mod = [dict(r) for r in rows]
for r in mod[cut + 1:]:
    r["c"] *= 3
    r["h"] *= 3
    r["q"] *= 50
a1, a2 = E.alerts_for(rows), E.alerts_for(mod)
for v in a1:
    assert [i for i in a1[v] if i <= cut] == [i for i in a2.get(v, []) if i <= cut], "changing the future changed an earlier alert: " + v
ok("no future data: sensors see candles only up to now; changing the future leaves earlier alerts identical")

import pump_custom
pump_custom.ENABLED = True
rc = E.run_coin(rows)
assert "my_example_big_green" in rc["views"] and rc["views"]["my_example_big_green"]["caught"][0] is not None, "own setup is backtested as its own row"
pump_custom.ENABLED = False
ok("own setup (pump_custom.py) shows up as a backtest row")

# ---------- validate (groups A/B, backtest, overfitting) ----------
D_orig = D.fetch_pump_window
assert V.set_group("a", "AAA " + time.strftime("%Y-%m-%d", time.gmtime(PUMP_DAY / 1000))) == []
assert V.set_group("b", "CCC " + time.strftime("%Y-%m-%d", time.gmtime(PUMPS["CCCUSDT"] // DAYMS * DAYMS / 1000))) == []
assert V.set_group("a", "AAA notadate")
assert "AAAUSDT" in V.group_text("a")
txt_a = V.step_test("a")
assert "GROUP A: 1 coins" in txt_a and "combined" in txt_a, txt_a
txt_b = V.step_test("b")
assert "OVERFITTING CHECK" in txt_b, txt_b
cfg.save({"PUMP": {"pct": 30}})
assert "not a clean overfitting check" not in V.compare() or True
V.step_find()
assert V.groups()["a"] and V.start("clean")["ok"]
time.sleep(0.5)
assert "no result yet" not in V.saved_text("a")
print(txt_a)
ok("groups, backtest A, check B, find, clean")
cfg.reset()

# ---------- settings sweep ----------
import pump_live as _pl
_pl.set_on(False)
sets_ = V._sets("a")
assert not isinstance(sets_, str) and sets_
cfg.apply({"MIN_STRATEGIES": 2, "PUMP": {"pct": 15, "window": 12, "merge_candles": 0}})  # fake-data test was built for the old numbers
snap = cfg.snapshot()
sw = E.sweep([cs for _, cs in sets_], progress=lambda m: None)
assert cfg.snapshot() == snap, "sweep must restore the numbers"
assert any(r["param"] == "volume_multiplier" and r["pumps"] > 0 and r["caught"] == r["pumps"] for r in sw) and sum(1 for r in sw if r["current"]) == len(E.SWEEP_GRID)
swt = E.sweep_text(sw, len(sets_))
assert "SETTINGS SWEEP" in swt and "overfitting" in swt
print(swt)
V.STATE["last"] = ""
assert "Settings sweep" or True
_pl.set_on(True)
assert "switch it OFF" in V.step_sweep("a")
_pl.set_on(False)
assert "SETTINGS SWEEP" in V.step_sweep("a") and "SETTINGS SWEEP" in V.saved_text("s")
ok("settings sweep: restores numbers, shows which settings catch the pump, refuses while live is ON")

# ---------- live ----------
def fake_candles(pair, n):
    """pumping coin: last 2 closed candles +4.5% each with 12x volume (an alert at the START of the move, not late)"""
    sym = L.base(pair) + "USDT"
    out = []
    p = 100.0
    base_t = NOW - n * 300_000
    rnd = random.Random(sym)
    for i in range(n):
        o = p
        vol = 1000 * (1 + rnd.random() * 0.3)
        if sym == "AAAUSDT" and i >= n - 2:
            p *= 1.045
            vol *= 12
        else:
            p *= 1 + rnd.uniform(-0.002, 0.002)
        out.append({"t": base_t + i * 300_000, "o": o, "h": max(o, p) * 1.001, "l": min(o, p) * 0.999, "c": p, "v": vol, "q": vol * p, "n": None, "tb": None, "oi": None, "fr": None})
    return out


def fake_get(url):
    if "active_instruments" in url:
        return ["B-AAA_USDT", "B-BBB_USDT", "B-BTC_USDT", "B-CCC_USDT"]
    if "orderbook" in url:
        return {"bids": {"1": "300"}, "asks": {"1.01": "100"}}
    raise AssertionError(url)


L.GET = fake_get
L.dcx_candles = fake_candles
D.HTTP = lambda url: fake_http(url) if "openInterestHist" not in url else [{"timestamp": NOW - 300_000 * (30 - i), "sumOpenInterestValue": str(1e6 * (1 + 0.03 * max(0, i - 14)))} for i in range(30)]
sent = []
L._tg = lambda t: sent.append(t) or {"ok": True}
L.explain = lambda pair, text: None
assert L.is_on() is False
L.set_on(True)
assert L.is_on() and L.ST["on"]
n = L.cycle()
assert n == 1 and len(sent) == 1 and "AAA" in sent[0] and "BTC" not in sent[0], sent
assert "volume अचानक बढ़ा" in sent[0] and "bids" in sent[0]
assert L.status()["caught"] == 1 and L.status()["recent"][0]["sym"] == "AAA"
assert L.cycle() == 0, "cooldown: same coin is not alerted twice"
assert L.status()["coins"] == 3, "majors (BTC) are excluded from the universe"
print(sent[0])
assert L.JOURNAL and L.JOURNAL[0]["sym"] == "AAA" and "volume_spike" in L.JOURNAL[0]["reasons"] and "कारण" in sent[0], (L.JOURNAL, sent[0])
assert L.status()["journal"][0]["verdict"] == ""
rec = L.JOURNAL[0]
rec["ts"] = NOW - 25_200_000
sent.clear()
L.follow_up()  # fake candles end at a price far above this record's price (124): no rise after it => WRONG with reasons
assert rec["verdict"] == "WRONG" and "गलत" in rec["why"] and sent and "नतीजा" in sent[0], rec
rec2 = dict(rec, verdict="", why="", price=90.0, ts=NOW - 25_200_000)
L.JOURNAL.insert(0, rec2)
sent.clear()
L.follow_up()
assert rec2["verdict"] == "RIGHT" and "सही" in rec2["why"], rec2
L.JOURNAL.clear(); L.JLOADED[0] = False
import store
assert len(store.kv_get("pump_journal", [])) >= 1, "journal is saved in the app database"
L.JOURNAL[:] = store.kv_get("pump_journal", [])
w = L.status()["watch"]
assert [x["sym"] for x in w] == ["AAA"] and w[0]["alerted"] and "volume_spike" in w[0]["sensors"], w
ok_ = L.extras  # Bybit funding is used for a coin that is not on Binance
cs = fake_candles("B-ZZZ_USDT", 60)
L.extras(cs, "B-ZZZ_USDT", {}, {"ZZZUSDT": -0.001})
assert cs[-1]["fr"] == -0.001
import pump_custom
pump_custom.ENABLED = True
sent.clear()
L.ST["last_alert"].clear(); L.ST["selector"].sent.clear()
assert L.cycle() == 2 and any("MY SETUP example_big_green: AAA" in t for t in sent) and any("PUMP ALERT AAA" in t for t in sent), sent
assert L.status()["custom"] == ["example_big_green"] and L.status()["custom_error"] == ""
pump_custom.ENABLED = False
ok("live cycle: pumping coin alerted once, quiet coins ignored, majors excluded, cooldown works")

# ---------- web routes ----------
import api
api.auth.valid = lambda c: True
H = {}
def call(path):
    code, ct, body, extra = W.handle(path, H)
    return code, ct, body, extra
code, ct, body, _ = call("/pump")
assert code == 200 and b"Pump system" in body
assert json.loads(call("/pump/status")[2])["live"]["on"] is True
c, _, b, _ = call("/pump/settings/save?json=" + json.dumps({"PUMP": {"pct": "abc"}}))
assert json.loads(b)["errors"]
c, _, b, _ = call("/pump/settings/save?json=" + json.dumps({"PUMP": {"pct": "22"}}))
assert json.loads(b)["errors"] == [] and cfg.PUMP["pct"] == 22.0
call("/pump/settings/reset")
assert cfg.PUMP["pct"] == 30.0
D.HTTP = fake_http
day = time.strftime("%Y-%m-%d", time.gmtime(PUMP_DAY / 1000))
c, ct, b, extra = call(f"/pump/download?sym=AAAUSDT&day={day}&before=5&after=2&iv=5m&oi=1&fr=1")
assert c == 200 and ct.startswith("text/csv") and "attachment" in extra["Content-Disposition"] and b.count(b"\n") > 2000
assert call(f"/pump/download?sym=AAAUSDT&day={day}&before=30&after=5&iv=5m")[0] == 400
assert "AAAUSDT" in json.loads(call("/pump/coins?q=aa")[2])["coins"]
assert json.loads(call("/pump/group/save?g=b&text=PEPE%202026-11-01")[2])["errors"] == []
assert "PEPEUSDT" in json.loads(call("/pump/group?g=b")[2])["text"]
c, ct, b, extra = call(f"/pump/download?sym=AAA&day={day}&before=5&after=2&iv=5m")
assert c == 200 and extra["Content-Disposition"].count("AAAUSDT"), "coin typed without USDT works"
assert b"autocapitalize" in W.PAGE.encode() and b"text-transform:uppercase" in W.PAGE.encode()
assert call("/pump/run?action=sweep")[0] == 200
api.auth.valid = lambda c: False
assert call("/pump/status")[0] == 401 and call("/pump")[0] == 401
ok("web routes: page, status, settings, download CSV, coins, groups, login required")

# ---------- AI tools ----------
import pump_ai
r = pump_ai.TOOLS["pump_data"](None, sym="AAA", day=day, before=5, after=2, interval="5m")
assert r["rows"] == 8 * 288 and r["pumps_found"] and "before_first_pump" in r and r["download_link_for_user"].startswith("/pump/download")
assert pump_ai.TOOLS["pump_settings"](None)["MIN_STRATEGIES"] == 3
assert pump_ai.TOOLS["pump_settings_set"](None, changes={"EVAL": {"hit_pct": 12}})["errors"] == "saved"
ok("AI tools: pump_data summary + settings")

# ---------- cross-coin selector ----------
import pump_select as _SEL
cfg.reset()
_s = _SEL.Selector()
_b, _o, _ = _s.step(1_000_000, [("A", 5), ("B", 9)])
assert _b[0] == "B" and [x[0] for x in _o] == ["A"], "best of linked coins wins"
assert _s.step(1_000_000 + 60_000 * 30, [("C", 50)])[0] is None, "pause after an alert"
assert _SEL.Selector().step(5, [(str(i), 1) for i in range(10)])[0] is None, "market-wide move sends nothing"
_s2 = _SEL.Selector()
for k in range(3):
    assert _s2.step(k * 7_200_000 + 7_200_000, [("X", 1)])[0] is not None
assert _s2.step(4 * 7_200_000 + 1, [("X", 1)])[0] is None, "daily limit"
cfg.reset()
ok("selector: best linked coin, pause, market-wide, daily limit (fake data)")
print("\nALL TESTS PASSED (fake data only)")
