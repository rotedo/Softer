"""Live toll booth. Nothing is saved: every 5 minutes the freshly closed 5m candles of the CoinDCX futures coins drive past the sensors,
unusual ones raise a Telegram alert, the rest are forgotten (only the last 30 alerts stay in memory for the /pump page).
 * CANDLES come only from CoinDCX. All other data (open interest, funding, order book) comes from other exchanges and is never used for charts.
 * Stage 1 (cheap, all coins): volume_spike + price_momentum on the last candles. Stage 2 (only the few that pass): open interest + funding + all sensors.
 * An alert needs at least MIN_STRATEGIES sensors. The Telegram alert goes out FIRST; the AI 'why is it rising' message follows as a 2nd message.
ON/OFF is saved in the app database (store.kv key 'pump_live'), default OFF, and survives restarts."""
import asyncio, json, logging, threading, time, urllib.request
from concurrent.futures import ThreadPoolExecutor
import pump_config as cfg
import pump_download as D
import pump_strategies as S

DCX, DCX_PUB = "https://api.coindcx.com", "https://public.coindcx.com"
STEP = 300_000
MAJORS = {"BTC", "ETH", "BNB", "XRP", "SOL", "USDC"}
ST = {"watch": {}, "on": None, "cycles": 0, "coins": 0, "caught": 0, "last_cycle_s": None, "last_error": "", "recent": [], "last_alert": {}}
U = {"t": 0, "pairs": [], "bn": {}, "bn_vol": {}}  # universe cache (refreshed hourly)


def GET(url):
    """plain JSON GET (replaceable in tests)"""
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 pump-system"})
    return json.load(urllib.request.urlopen(req, timeout=20))


def is_on():
    if ST["on"] is None:
        try:
            import store
            ST["on"] = bool(store.kv_get("pump_live", False))
        except Exception:
            ST["on"] = False
    return ST["on"]


def set_on(on):
    ST["on"] = bool(on)
    try:
        import store
        store.kv_set("pump_live", ST["on"])
    except Exception:
        pass


WATCH_MIN = 120  # a coin stays on the watch list this long after it last showed a sensor


def status():
    now = time.time()
    watch = sorted(({"sym": base(p), "since_min": round((now - w["since"]) / 60), "sensors": w["sensors"], "alerted": w["alerted"]} for p, w in ST["watch"].items()), key=lambda w: w["since_min"])
    return {"watch": watch, "custom": list(S.CUSTOM), "custom_error": S.CUSTOM_ERROR, "on": is_on(), "cycles": ST["cycles"], "coins": ST["coins"], "caught": ST["caught"], "last_cycle_s": ST["last_cycle_s"],
            "last_error": ST["last_error"], "recent": ST["recent"][:30]}


def base(pair):  # B-PEPE_USDT -> PEPE
    return pair.split("-", 1)[1].rsplit("_", 1)[0]


def bn_symbol(b):
    for s in (b + "USDT", "1000" + b + "USDT", "1000000" + b + "USDT"):
        if s in U["bn_vol"]:
            return s
    return None


def refresh_universe():
    """CoinDCX futures pairs (+ Binance 24h volume as the liquidity filter where the coin exists there)"""
    if time.time() - U["t"] < 3600 and U["pairs"]:
        return
    ins = GET(f"{DCX}/exchange/v1/derivatives/futures/data/active_instruments?margin_currency_short_name[]=USDT")
    pairs = [p if isinstance(p, str) else (p.get("pair") or p.get("symbol")) for p in ins]
    pairs = [p for p in pairs if p and p.startswith("B-") and p.endswith("_USDT") and base(p) not in MAJORS]
    try:
        U["bn_vol"] = {t["symbol"]: float(t["quoteVolume"]) for t in D.HTTP(D.BASE + "/fapi/v1/ticker/24hr")}
    except Exception as e:  # liquidity filter is optional
        logging.warning("binance 24h volume failed: %s", e)
        U["bn_vol"] = {}
    keep = []
    for p in pairs:
        s = bn_symbol(base(p))
        if s is None or U["bn_vol"].get(s, 0) >= cfg.LIVE["min_quote_vol_24h"]:
            keep.append(p)
    U["pairs"], U["t"] = keep, time.time()


def dcx_candles(pair, n):
    """last n CLOSED 5m candles of one CoinDCX futures pair, oldest first"""
    t1 = int(time.time())
    d = GET(f"{DCX_PUB}/market_data/candlesticks?pair={pair}&from={t1 - (n + 3) * 300}&to={t1}&resolution=5&pcode=f")
    out, now = [], int(time.time() * 1000)
    for k in d["data"] if isinstance(d, dict) else d:
        t = int(k["time"])
        t = t * 1000 if t < 1e11 else t
        if t + STEP > now:  # still forming
            continue
        o, h, l, c, v = (float(k[x]) for x in ("open", "high", "low", "close", "volume"))
        out.append({"t": t, "o": o, "h": h, "l": l, "c": c, "v": v, "q": v * c, "n": None, "tb": None, "oi": None, "fr": None})
    out.sort(key=lambda r: r["t"])
    return out[-n:]


def bybit_funding():
    """funding rate of every Bybit perp in one call (used for coins that are not on Binance)"""
    try:
        d = GET("https://api.bybit.com/v5/market/tickers?category=linear")
        return {t["symbol"]: float(t["fundingRate"]) for t in d["result"]["list"] if t.get("fundingRate") not in (None, "")}
    except Exception:
        return {}


def extras(c, pair, fund, byb):
    """stage 2: put open interest (Binance) and funding (Binance, else Bybit) on the candles. Nothing is stored."""
    sym, b = bn_symbol(base(pair)), base(pair)
    if sym:
        try:
            h = D.HTTP(f"{D.BASE}/futures/data/openInterestHist?symbol={sym}&period=5m&limit=30")
            pts = sorted((int(r["timestamp"]), float(r["sumOpenInterestValue"])) for r in h)
            D._asof(c, pts, "oi", STEP)
        except Exception:
            pass
    fr = fund.get(sym) if sym else None
    if fr is None:
        fr = next((byb[x] for x in (b + "USDT", "1000" + b + "USDT") if x in byb), None)
    if fr is not None:
        for x in c[-20:]:
            x["fr"] = fr


def book_imbalance(pair):
    """share of bid volume in the top 50 CoinDCX levels (0.5 = balanced), or None"""
    try:
        d = GET(f"{DCX_PUB}/market_data/v3/orderbook/{pair}-futures/50")
        val = lambda side: sum(float(p) * float(q) for p, q in (side.items() if isinstance(side, dict) else [(l[0], l[1]) if isinstance(l, (list, tuple)) else (l["price"], l["quantity"]) for l in side]))
        b, a = val(d["bids"]), val(d["asks"])
        return round(b / (a + b), 2) if a + b else None
    except Exception:
        return None


def alert_text(pair, c, res, imb):
    ok = {k: n for k, (b, n) in res.items() if b}
    px = (c[-1]["c"] / c[-13]["c"] - 1) * 100 if len(c) > 13 else 0
    lines = [f"🚨 PUMP ALERT {base(pair)} (CoinDCX)", f"price {c[-1]['c']:g} | 1h {px:+.1f}% | sensors {len(ok)}/{len(res)}"]
    lines += [f"- {k}: {n}" for k, n in ok.items()]
    if imb is not None:
        lines.append(f"- order book: {int(imb * 100)}% bids")
    lines.append("(automatic scan, not advice)")
    return "\n".join(lines)


def _tg(text):
    try:
        import archive
        return archive.tg_message(text)
    except Exception as e:
        return {"ok": False, "error": str(e)}


def explain(pair, text):
    """2nd message: AI looks for possible reasons. Runs in its own thread so the alert is never delayed."""
    try:
        import agents, llm
        e = agents.keys()
        if not e:
            return
        q = f"Why might the crypto coin {base(pair)} be pumping right now? Recent news, listings, partnerships, social buzz."
        web = llm.web_context(e, q)
        ans = llm.complete(e, "You are a crypto analyst. In 5 short bullet lines, give possible reasons this coin is rising now. Say clearly when you are unsure. Reply in Hindi.",
                           f"Alert:\n{text}\n\nWeb notes:\n{web or 'none'}\n\n{q}", timeout=60)
        _tg(f"🔎 {base(pair)}: संभावित कारण\n{ans}"[:3900])
    except Exception as ex:
        logging.warning("pump explain failed: %s", ex)


def cycle():
    """one pass over the whole universe. -> number of alerts"""
    t0 = time.time()
    cfg.load_saved()
    refresh_universe()
    n, errors, stage2 = int(cfg.LIVE["klines"]), [0], []

    def stage1(pair):
        try:
            c = dcx_candles(pair, n)
            if len(c) < 50:
                return None
            res = S.run_all(c, only=("volume_spike", "price_momentum"))
            hit = [k for k, (b, _) in res.items() if b]
            mine = {k: nt for k, (b, nt) in S.run_custom(c).items() if b}
            return (pair, c, hit, mine) if hit or mine else None
        except Exception:
            errors[0] += 1
            return None

    with ThreadPoolExecutor(max_workers=int(cfg.LIVE["workers"])) as ex:
        for r in ex.map(stage1, U["pairs"]):
            if r:
                stage2.append(r)
    ST["last_error"] = f"CoinDCX candles failed for {errors[0]}/{len(U['pairs'])} coins" if U["pairs"] and errors[0] > len(U["pairs"]) / 2 else ""
    now = time.time()
    for pair, _, hit, _ in stage2:  # AI-free watch list: coins that show a sensor now stay listed for WATCH_MIN minutes
        w = ST["watch"].setdefault(pair, {"since": now, "seen": now, "sensors": [], "alerted": False})
        w["seen"], w["sensors"] = now, hit
    for p in [p for p, w in ST["watch"].items() if now - w["seen"] > WATCH_MIN * 60]:
        del ST["watch"][p]
    fund, byb = {}, {}
    if any(hit for _, _, hit, _ in stage2):
        try:
            fund = {r["symbol"]: float(r["lastFundingRate"]) for r in D.HTTP(D.BASE + "/fapi/v1/premiumIndex")}
        except Exception:
            pass
        byb = bybit_funding()
    sent = 0
    for pair, c, hit, mine in stage2:
        for name, note in mine.items():  # your own setups (pump_custom.py): alert on their own
            key = (pair, name)
            if time.time() - ST["last_alert"].get(key, 0) >= cfg.LIVE["cooldown_min"] * 60:
                ST["last_alert"][key] = time.time()
                _tg(f"🎯 MY SETUP {name}: {base(pair)} (CoinDCX)\nprice {c[-1]['c']:g}\n{note}")
                ST["recent"].insert(0, {"ts": int(time.time() * 1000), "sym": base(pair), "score": 0, "price": c[-1]["c"], "reasons": {"my_" + name: note}})
                sent += 1
        if not hit:
            continue
        extras(c, pair, fund, byb)
        res = S.run_all(c)
        if sum(1 for b, _ in res.values() if b) < cfg.MIN_STRATEGIES:
            continue
        if time.time() - ST["last_alert"].get(pair, 0) < cfg.LIVE["cooldown_min"] * 60:
            continue
        ST["last_alert"][pair] = time.time()
        ST["watch"].setdefault(pair, {"since": now, "seen": now, "sensors": hit, "alerted": True})["alerted"] = True
        text = alert_text(pair, c, res, book_imbalance(pair))
        _tg(text)
        ST["recent"].insert(0, {"ts": int(time.time() * 1000), "sym": base(pair), "score": round(100 * sum(1 for b, _ in res.values() if b) / max(1, len(res))),
                                "price": c[-1]["c"], "reasons": {k: n_ for k, (b, n_) in res.items() if b}})
        ST["caught"] += 1
        sent += 1
        threading.Thread(target=explain, args=(pair, text), daemon=True).start()
    del ST["recent"][30:]
    ST["cycles"] += 1
    ST["coins"] = len(U["pairs"])
    ST["last_cycle_s"] = round(time.time() - t0, 1)
    return sent


async def loop():
    """runs 24x7 with the server; scans only while ON"""
    cfg.load_saved()
    while True:
        now = time.time()
        nxt = (int(now // 300) + 1) * 300 + float(cfg.LIVE["delay_s"])
        await asyncio.sleep(max(1.0, nxt - now))
        if not is_on():
            continue
        try:
            await asyncio.get_running_loop().run_in_executor(None, cycle)
        except Exception as e:
            ST["last_error"] = f"{type(e).__name__}: {e}"[:160]
            logging.exception("pump live cycle failed")
