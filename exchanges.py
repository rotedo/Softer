"""Per-exchange feed specs + parsers -> unified rows (see collector.SCHEMA).

Unified conventions: sym = BASE+USDT (BTCUSDT) | qty always in BASE coin | side = taker/aggressor side (buy/sell)
liqs.side = side of the POSITION that got liquidated (long/short) | book depth = notional within 10 bps of mid.
"""
import asyncio, functools, random, time
import collector as c
import extras as x

fo, now = c.fo, c.now
M15 = 900_000
CTVAL = {}  # (venue, raw_symbol) -> base units per contract (OKX, Delta). Missing -> parse error (no bad data stored)

BN = "https://fapi.binance.com"
BY = "https://api.bybit.com"
OK = "https://www.okx.com"
BG = "https://api.bitget.com"
DL = "https://api.india.delta.exchange"
DCX = "https://api.coindcx.com"
DCX_PUB = "https://public.coindcx.com"


def ct(v, raw):
    return CTVAL[(v, raw)]


def lvl(levels, mult=1.0):
    return [(float(l[0]), float(l[1]) * mult) for l in levels]


def book_row(ts, v, sym, bids, asks, bps=10):
    """bids/asks [(price, qty_base)] -> ("book", (ts, venue, sym, bid, ask, bid_depth, ask_depth, imbalance))."""
    bids, asks = sorted(bids, reverse=True), sorted(asks)
    if not bids or not asks:
        return []
    mid = (bids[0][0] + asks[0][0]) / 2
    lim = mid * bps / 1e4
    bd = sum(p * q for p, q in bids if p >= mid - lim)
    ad = sum(p * q for p, q in asks if p <= mid + lim)
    return [("book", (ts, v, sym, bids[0][0], asks[0][0], bd, ad, (bd - ad) / (bd + ad) if bd + ad else 0.0))]


def kl_row(v, sym, ts_open, o, h, l, cl, vol, qv, n=None, tbv=None):
    return ("klines", (int(float(ts_open)), v, sym, fo(o), fo(h), fo(l), fo(cl), fo(vol), fo(qv), n, fo(tbv)))


# ---------------- Binance (USDT-M futures) ----------------
def p_bn_premium(d, ts):
    return [("funding", (i["time"], "binance", i["symbol"], fo(i["lastFundingRate"]), fo(i["markPrice"]),
                         fo(i["indexPrice"]), i["nextFundingTime"]))
            for i in d if i["symbol"].endswith("USDT") and "_" not in i["symbol"]]


def p_bn_oi(d, ts, **k):
    return [("oi", (d["time"], "binance", d["symbol"], fo(d["openInterest"]), None))]


def p_bn_depth(d, ts, sym):
    return book_row(ts, "binance", sym, lvl(d["bids"]), lvl(d["asks"]))


def p_bn_kl(d, ts, sym):
    return [x.norm_kline(sym, k) for k in d if k[6] < ts]


def p_bn_ls(d, ts, sym):
    return [("ls", (i["timestamp"], "binance", i["symbol"], fo(i["longShortRatio"]), fo(i["longAccount"]), fo(i["shortAccount"]))) for i in d]


def w_binance(m):
    d = m.get("data", m)
    e = d.get("e")
    if e == "aggTrade":
        return [("trades", (d["T"], "binance", "perp", d["s"], float(d["p"]), float(d["q"]), "sell" if d["m"] else "buy", str(d["a"]))) ]
    if e == "forceOrder":
        o = d["o"]
        if not o["s"].endswith("USDT"):
            return []
        p, q = float(o["ap"]) or float(o["p"]), float(o["z"]) or float(o["q"])
        return [("liqs", (o["T"], "binance", o["s"], "long" if o["S"] == "SELL" else "short", p, q, p * q))]
    return []


# ---------------- Bybit (v5 linear) ----------------
def p_by_tickers(d, ts):
    out = []
    for i in d["result"]["list"]:
        s = i["symbol"]
        if s.endswith("USDT"):
            out.append(("funding", (ts, "bybit", s, fo(i.get("fundingRate")), fo(i.get("markPrice")), fo(i.get("indexPrice")), fo(i.get("nextFundingTime")))))
            out.append(("oi", (ts, "bybit", s, fo(i.get("openInterest")), fo(i.get("openInterestValue")))))
    return out


def p_by_depth(d, ts, sym):
    r = d["result"]
    return book_row(ts, "bybit", sym, lvl(r["b"]), lvl(r["a"]))


def p_by_kl(d, ts, sym):  # newest first: [start,o,h,l,c,vol,turnover]
    return [kl_row("bybit", sym, k[0], k[1], k[2], k[3], k[4], k[5], k[6]) for k in d["result"]["list"] if int(k[0]) + M15 <= ts]


def p_by_ls(d, ts, sym):
    out = []
    for i in d["result"]["list"]:
        b, s = fo(i["buyRatio"]), fo(i["sellRatio"])
        out.append(("ls", (int(i["timestamp"]), "bybit", sym, b / s if s else None, b, s)))
    return out


def w_bybit(m):
    t = m.get("topic", "")
    if t.startswith("publicTrade."):
        return [("trades", (int(i["T"]), "bybit", "perp", i["s"], float(i["p"]), float(i["v"]), "buy" if i["S"] == "Buy" else "sell", i["i"])) for i in m["data"]]
    if t.startswith("allLiquidation."):  # S=Buy means a LONG was liquidated
        return [("liqs", (int(i["T"]), "bybit", i["s"], "long" if i["S"] == "Buy" else "short", float(i["p"]), float(i["v"]), float(i["p"]) * float(i["v"]))) for i in m["data"]]
    return []


# ---------------- OKX (v5 SWAP) ----------------
def osym(inst):
    return inst.split("-")[0] + "USDT"


def p_ok_oi(d, ts):
    return [("oi", (int(i["ts"]), "okx", osym(i["instId"]), fo(i["oiCcy"]), fo(i["oiUsd"]))) for i in d["data"] if i["instId"].endswith("-USDT-SWAP")]


def p_ok_fund(d, ts, inst):
    i = d["data"][0]
    return [("funding", (ts, "okx", osym(inst), fo(i["fundingRate"]), None, None, fo(i["nextFundingTime"]))) ]


def p_ok_depth(d, ts, inst):
    r, m = d["data"][0], ct("okx", inst)
    return book_row(ts, "okx", osym(inst), lvl(r["bids"], m), lvl(r["asks"], m))


def p_ok_kl(d, ts, inst):  # [ts,o,h,l,c,vol(contracts),volCcy(base),volCcyQuote,confirm]
    return [kl_row("okx", osym(inst), k[0], k[1], k[2], k[3], k[4], k[6], k[7]) for k in d["data"] if k[8] == "1"]


def p_ok_ls(d, ts, base):
    out = []
    for r in sorted(d["data"], key=lambda r: int(r[0]))[-1:]:  # newest 5m bucket only
        q = fo(r[1])
        out.append(("ls", (int(r[0]), "okx", base + "USDT", q, q / (1 + q), 1 / (1 + q))))
    return out


def w_okx(m):
    ch, out = m.get("arg", {}).get("channel"), []
    if ch == "trades":
        for i in m.get("data", []):
            out.append(("trades", (int(i["ts"]), "okx", "perp", osym(i["instId"]), float(i["px"]), float(i["sz"]) * ct("okx", i["instId"]), i["side"], i["tradeId"])))
    elif ch == "liquidation-orders":
        for r in m.get("data", []):
            if not r["instId"].endswith("-USDT-SWAP"):
                continue
            for dt in r.get("details", []):
                p, q = float(dt["bkPx"]), float(dt["sz"]) * ct("okx", r["instId"])
                pos = dt.get("posSide")
                long_ = (pos == "long") if pos in ("long", "short") else dt["side"] == "sell"
                out.append(("liqs", (int(dt["ts"]), "okx", osym(r["instId"]), "long" if long_ else "short", p, q, p * q)))
    return out


# ---------------- Bitget (v2 USDT-FUTURES) ----------------
def p_bg_tickers(d, ts):
    out = []
    for i in d["data"]:
        s, t = i["symbol"], int(i.get("ts") or ts)
        out.append(("funding", (t, "bitget", s, fo(i.get("fundingRate")), fo(i.get("markPrice")), fo(i.get("indexPrice")), None)))
        out.append(("oi", (t, "bitget", s, fo(i.get("holdingAmount")), None)))
    return out


def p_bg_depth(d, ts, sym):
    r = d["data"]
    return book_row(ts, "bitget", sym, lvl(r["bids"]), lvl(r["asks"]))


def p_bg_kl(d, ts, sym):  # ascending [ts,o,h,l,c,baseVol,quoteVol]
    return [kl_row("bitget", sym, k[0], k[1], k[2], k[3], k[4], k[5], k[6]) for k in d["data"] if int(k[0]) + M15 <= ts]


def w_bitget(m):
    if m.get("arg", {}).get("channel") != "trade":
        return []
    s = m["arg"]["instId"]
    return [("trades", (int(i["ts"]), "bitget", "perp", s, float(i["price"]), float(i["size"]), i["side"], i["tradeId"])) for i in m.get("data", [])]


# ---------------- Delta Exchange India ----------------
def dsym(raw):
    return (raw[:-3] if raw.endswith("USD") else raw) + "USDT"


def p_dl_tickers(d, ts):
    out = []
    for i in d["result"]:
        raw = i["symbol"]
        sym = dsym(raw)
        t = int(fo(i.get("timestamp")) // 1000) if i.get("timestamp") else ts
        out.append(("funding", (t, "delta", sym, fo(i.get("funding_rate")), fo(i.get("mark_price")), fo(i.get("spot_price")), None)))
        out.append(("oi", (t, "delta", sym, fo(i.get("oi")), fo(i.get("oi_value_usd")))))
    return out


def _dl_lv(levels, m):
    out = []
    for l in levels:
        if isinstance(l, dict):
            p, q = l.get("limit_price", l.get("price")), l.get("size", l.get("quantity"))
        else:
            p, q = l[0], l[1]
        out.append((float(p), float(q) * m))
    return out


def p_dl_depth(d, ts, raw):
    r, m = d["result"], ct("delta", raw)
    return book_row(ts, "delta", dsym(raw), _dl_lv(r["buy"], m), _dl_lv(r["sell"], m))


def p_dl_kl(d, ts, raw):
    m = ct("delta", raw)
    return [kl_row("delta", dsym(raw), k["time"] * 1000, k["open"], k["high"], k["low"], k["close"], float(k["volume"]) * m, None)
            for k in d["result"] if k["time"] * 1000 + M15 <= ts]


def w_delta(m):
    if m.get("type") != "all_trades":
        return []
    raw = m["symbol"]
    return [("trades", (int(m["timestamp"]) // 1000, "delta", "perp", dsym(raw), float(m["price"]), float(m["size"]) * ct("delta", raw),
                        "buy" if m.get("buyer_role") == "taker" else "sell", f"{m['timestamp']}:{m['price']}:{m['size']}"))]


# ---------------- CoinDCX futures ----------------
def dcx_sym(pair):  # B-BTC_USDT -> BTCUSDT
    return pair.split("-", 1)[1].replace("_", "")


def _lv(v):
    if isinstance(v, dict):
        return [(float(p), float(q)) for p, q in v.items()]
    return [(float(l[0]), float(l[1])) if isinstance(l, (list, tuple)) else (float(l["price"]), float(l["quantity"])) for l in v]


def p_dcx_depth(d, ts, pair):
    return book_row(ts, "coindcx", dcx_sym(pair), _lv(d["bids"]), _lv(d["asks"]))


def p_dcx_trades(d, ts, pair):
    out = []
    for i in d:
        p, q = fo(i.get("price", i.get("p"))), fo(i.get("quantity", i.get("q")))
        t = int(i.get("timestamp", i.get("T", ts)))
        t = t * 1000 if t < 1e11 else t
        out.append(("trades", (t, "coindcx", "perp", dcx_sym(pair), p, q, "sell" if i.get("is_maker", i.get("m")) else "buy", f"{t}:{p}:{q}")))
    return out


def p_dcx_kl(d, ts, pair):
    out = []
    for k in d["data"] if isinstance(d, dict) else d:
        t = int(k["time"])
        t = t * 1000 if t < 1e11 else t
        if t + M15 <= ts:
            out.append(kl_row("coindcx", dcx_sym(pair), t, k["open"], k["high"], k["low"], k["close"], k["volume"], None))
    return out


def dcx_inr_rate(d):
    return next(float(i["last_price"]) for i in d if i["market"] == "USDTINR")


def dcx_pair_list(ins):
    pairs = [p if isinstance(p, str) else (p.get("pair") or p.get("symbol")) for p in ins]
    return [p for p in pairs if p and p.startswith("B-") and p.endswith("_USDT")]


async def tier_scan_dcx(sink, state, inr=1_000_000, max_bps=10, every=900, once=False, get=c.aget, delay=0.15):
    """Tier 1: CoinDCX futures pairs where a Rs `inr` market order slips <= max_bps on both sides. 15m candles for passers."""
    for n in ("scan", "instruments", "ticker", "depth", "klines"):
        c.stat(f"rest-coindcx-{n}", "rest")["max_age_s"] = every * 2 + 120
    while True:
        try:
            pairs = dcx_pair_list(await get(f"{DCX}/exchange/v1/derivatives/futures/data/active_instruments?margin_currency_short_name[]=USDT", "rest-coindcx-instruments"))
            usd = inr / dcx_inr_rate(await get(f"{DCX}/exchange/ticker", "rest-coindcx-ticker"))
            passed = {}
            for pair in pairs:
                sym = dcx_sym(pair)
                try:
                    d = await get(f"{DCX_PUB}/market_data/v3/orderbook/{pair}-futures/50", "rest-coindcx-depth")
                    b, s, ok = x.eval_depth({"bids": sorted(_lv(d["bids"]), reverse=True), "asks": sorted(_lv(d["asks"]))}, usd, max_bps)
                    sink.put([("scan", (c.now(), "coindcx", sym, None, b, s, ok))])
                    if ok:
                        passed[sym] = pair
                    c.note("rest-coindcx-scan", lat=0)
                except Exception as e:
                    c.stat("rest-coindcx-scan", "rest")["last_err"] = f"{pair}: {e}"[:80]
                await asyncio.sleep(delay)
            state["tier1"] = list(passed)
            for sym, pair in passed.items():
                try:
                    t = int(time.time())
                    d = await get(f"{DCX_PUB}/market_data/candlesticks?pair={pair}&from={t - 3 * 900}&to={t}&resolution=15&pcode=f", "rest-coindcx-klines")
                    sink.put(p_dcx_kl(d, c.now(), pair))
                except Exception as e:
                    c.stat("rest-coindcx-scan", "rest")["last_err"] = f"kl {pair}: {e}"[:80]
                await asyncio.sleep(delay)
        except Exception as e:
            c.stat("rest-coindcx-scan", "rest")["last_err"] = str(e)[:80]
        if once:
            return
        await asyncio.sleep(every)


# ---------------- contract sizes (OKX / Delta quote contracts, not coins) ----------------
async def load_ctvals(get=c.aget):
    d = await get(f"{OK}/api/v5/public/instruments?instType=SWAP", "rest-okx-instruments")
    for i in d["data"]:
        if i["instId"].endswith("-USDT-SWAP"):
            CTVAL[("okx", i["instId"])] = float(i["ctVal"]) * float(i.get("ctMult") or 1)
    d = await get(f"{DL}/v2/products?contract_types=perpetual_futures", "rest-delta-products")
    for i in d["result"]:
        if i.get("contract_value"):
            CTVAL[("delta", i["symbol"])] = float(i["contract_value"])


async def ctval_loop(get=c.aget):
    for n in ("rest-okx-instruments", "rest-delta-products"):
        c.stat(n, "rest")["max_age_s"] = 13 * 3600
    while True:
        try:
            await load_ctvals(get)
            await asyncio.sleep(6 * 3600)
        except Exception:
            await asyncio.sleep(30)


# ---------------- feed specs ----------------
def rest_feeds(wish, venues):
    """Each feed: poll `url` (str or callable) and parse -> rows. live/lite = poll seconds when live-watching vs idle."""
    F = []

    wsyms = {b + "USDT" for b in wish}

    def add(v, ep, url, parse, live, lite, bulk=False):
        # bulk = all-symbol endpoint: wishlist symbols stored every poll, every other symbol only every 5 min (keeps DB small)
        F.append(dict(name=f"rest-{v}-{ep}", venue=v, url=url, parse=parse, live=live, lite=lite, bulk=wsyms if bulk else None))
    P = functools.partial
    if "binance" in venues:
        add("binance", "funding", f"{BN}/fapi/v1/premiumIndex", p_bn_premium, 30, 300, bulk=True)
        for b in wish:
            s = b + "USDT"
            add("binance", f"book-{b}", f"{BN}/fapi/v1/depth?symbol={s}&limit=100", P(p_bn_depth, sym=s), 3, 30)
            add("binance", f"oi-{b}", f"{BN}/fapi/v1/openInterest?symbol={s}", p_bn_oi, 10, 120)
            add("binance", f"kl-{b}", f"{BN}/fapi/v1/klines?symbol={s}&interval=15m&limit=3", P(p_bn_kl, sym=s), 60, 900)
            add("binance", f"ls-{b}", f"{BN}/futures/data/globalLongShortAccountRatio?symbol={s}&period=5m&limit=1", P(p_bn_ls, sym=s), 60, 300)
    if "bybit" in venues:
        add("bybit", "tickers", f"{BY}/v5/market/tickers?category=linear", p_by_tickers, 10, 120, bulk=True)
        for b in wish:
            s = b + "USDT"
            add("bybit", f"book-{b}", f"{BY}/v5/market/orderbook?category=linear&symbol={s}&limit=50", P(p_by_depth, sym=s), 2, 30)
            add("bybit", f"kl-{b}", f"{BY}/v5/market/kline?category=linear&symbol={s}&interval=15&limit=3", P(p_by_kl, sym=s), 60, 900)
            add("bybit", f"ls-{b}", f"{BY}/v5/market/account-ratio?category=linear&symbol={s}&period=5min&limit=1", P(p_by_ls, sym=s), 60, 300)
    if "okx" in venues:
        add("okx", "oi", f"{OK}/api/v5/public/open-interest?instType=SWAP", p_ok_oi, 15, 120, bulk=True)
        for b in wish:
            i = f"{b}-USDT-SWAP"
            add("okx", f"book-{b}", f"{OK}/api/v5/market/books?instId={i}&sz=50", P(p_ok_depth, inst=i), 2, 30)
            add("okx", f"funding-{b}", f"{OK}/api/v5/public/funding-rate?instId={i}", P(p_ok_fund, inst=i), 30, 300)
            add("okx", f"kl-{b}", f"{OK}/api/v5/market/candles?instId={i}&bar=15m&limit=3", P(p_ok_kl, inst=i), 60, 900)
            add("okx", f"ls-{b}", f"{OK}/api/v5/rubik/stat/contracts/long-short-account-ratio?ccy={b}&period=5m&limit=1", P(p_ok_ls, base=b), 60, 300)
    if "bitget" in venues:
        add("bitget", "tickers", f"{BG}/api/v2/mix/market/tickers?productType=USDT-FUTURES", p_bg_tickers, 10, 120, bulk=True)
        for b in wish:
            s = b + "USDT"
            add("bitget", f"book-{b}", f"{BG}/api/v2/mix/market/merge-depth?symbol={s}&productType=USDT-FUTURES&limit=50", P(p_bg_depth, sym=s), 2, 30)
            add("bitget", f"kl-{b}", f"{BG}/api/v2/mix/market/candles?symbol={s}&productType=USDT-FUTURES&granularity=15m&limit=3", P(p_bg_kl, sym=s), 60, 900)
    if "delta" in venues:
        add("delta", "tickers", f"{DL}/v2/tickers?contract_types=perpetual_futures", p_dl_tickers, 10, 120, bulk=True)
        for b in wish:
            r = b + "USD"
            add("delta", f"book-{b}", f"{DL}/v2/l2orderbook/{r}?depth=50", P(p_dl_depth, raw=r), 2, 30)
            add("delta", f"kl-{b}", lambda r=r: f"{DL}/v2/history/candles?resolution=15m&symbol={r}&start={int(time.time()) - 3 * 900}&end={int(time.time())}", P(p_dl_kl, raw=r), 60, 900)
    if "coindcx" in venues:
        for b in wish:
            p = f"B-{b}_USDT"
            add("coindcx", f"book-{b}", f"{DCX_PUB}/market_data/v3/orderbook/{p}-futures/50", P(p_dcx_depth, pair=p), 2, 30)
            add("coindcx", f"trades-{b}", f"{DCX}/exchange/v1/derivatives/futures/data/trades?pair={p}", P(p_dcx_trades, pair=p), 3, 60)
            add("coindcx", f"kl-{b}", lambda p=p: f"{DCX_PUB}/market_data/candlesticks?pair={p}&from={int(time.time()) - 3 * 900}&to={int(time.time())}&resolution=15&pcode=f", P(p_dcx_kl, pair=p), 60, 900)
    return F


def ws_feeds(wish, venues):
    W = []
    if "binance" in venues:
        st = "/".join(f"{b.lower()}usdt@aggTrade" for b in wish) + "/!forceOrder@arr"
        W.append(dict(name="ws-binance", url=f"wss://fstream.binance.com/market/stream?streams={st}", subs=[], parse=w_binance))
    if "bybit" in venues:
        a = [f"publicTrade.{b}USDT" for b in wish] + [f"allLiquidation.{b}USDT" for b in wish]
        W.append(dict(name="ws-bybit", url="wss://stream.bybit.com/v5/public/linear", subs=[{"op": "subscribe", "args": a}], parse=w_bybit, app_ping={"op": "ping"}))
    if "okx" in venues:
        a = [{"channel": "trades", "instId": f"{b}-USDT-SWAP"} for b in wish] + [{"channel": "liquidation-orders", "instType": "SWAP"}]
        W.append(dict(name="ws-okx", url="wss://ws.okx.com:8443/ws/v5/public", subs=[{"op": "subscribe", "args": a}], parse=w_okx, app_ping="ping"))
    if "bitget" in venues:
        a = [{"instType": "USDT-FUTURES", "channel": "trade", "instId": f"{b}USDT"} for b in wish]
        W.append(dict(name="ws-bitget", url="wss://ws.bitget.com/v2/ws/public", subs=[{"op": "subscribe", "args": a}], parse=w_bitget, app_ping="ping", ping_every=25))
    if "delta" in venues:
        W.append(dict(name="ws-delta", url="wss://socket.india.delta.exchange",
                      subs=[{"type": "subscribe", "payload": {"channels": [{"name": "all_trades", "symbols": [f"{b}USD" for b in wish]}]}}], parse=w_delta))
    return W


async def run_rest(sink, feed, state, once=False, get=c.aget):
    st = c.stat(feed["name"], "rest")
    st["max_age_s"] = feed["lite"] * 2 + 30
    if not once:
        await asyncio.sleep(random.random() * 5)  # stagger start
    while True:
        try:
            d = await get(feed["url"], feed["name"])
            try:
                rows = feed["parse"](d, c.now())
                if feed.get("bulk") is not None:
                    t = c.now()
                    full = t - st.get("last_full", 0) >= 300_000
                    if full:
                        st["last_full"] = t
                    rows = [r for r in rows if full or r[1][2] in feed["bulk"]]
                if rows:
                    sink.put(rows)
                st["rows"] = len(rows)
            except Exception as e:
                st["errors"] += 1
                st["last_err"] = f"parse: {type(e).__name__} {e}"[:80]
        except Exception as e:
            if "418" in str(e) or "429" in str(e):  # exchange rate-limit / temporary IP ban: back off hard
                if once:
                    return
                await asyncio.sleep(120)
        if once:
            return
        await asyncio.sleep(feed["live"] if state.get("live") else feed["lite"])
