"""REST pollers: tier-1 liquidity scan + 15m klines, Deribit options, long/short ratio, retention purge."""
import asyncio, json, logging, time, urllib.request
from datetime import datetime, timezone
import collector as c

log = logging.getLogger("extras")
FAPI = "https://fapi.binance.com"
RET_MS = {"trades": 7 * 864e5, "flow": 14 * 864e5, "book": 864e5, "liqs": 7 * 864e5, "funding": 7 * 864e5, "oi": 7 * 864e5,
          "options": 7 * 864e5, "ls": 30 * 864e5, "scan": 7 * 864e5, "klines": 30 * 864e5}


async def aget(url, name="rest"):
    def _get():
        req = urllib.request.Request(url, headers={"User-Agent": "orderflow-collector/1.0"})
        return json.load(urllib.request.urlopen(req, timeout=15))
    t = time.time()
    try:
        d = await asyncio.get_running_loop().run_in_executor(None, _get)
        c.note(name, lat=int((time.time() - t) * 1000))  # REST round-trip ms
        return d
    except Exception:
        c.stat(name, "rest")["errors"] += 1
        raise


# ---- tier 1: liquidity filter ----
def fill_bps(levels, usd, mid):
    rem, qty = float(usd), 0.0
    for p, q in levels:
        p, q = float(p), float(q)
        n = min(rem, p * q)
        qty += n / p
        rem -= n
        if rem <= 1e-9:
            break
    if rem > 1e-6 or qty == 0:
        return None  # book too thin for this size
    return abs(usd / qty - mid) / mid * 1e4


def eval_depth(d, usd, max_bps):
    mid = (float(d["bids"][0][0]) + float(d["asks"][0][0])) / 2
    b, s = fill_bps(d["asks"], usd, mid), fill_bps(d["bids"], usd, mid)
    return b, s, int(b is not None and s is not None and max(b, s) <= max_bps)


def norm_kline(sym, k):
    return ("klines", (k[0], "binance", sym, float(k[1]), float(k[2]), float(k[3]), float(k[4]),
                       float(k[5]), float(k[7]), int(k[8]), float(k[9])))


async def tier_scan(sink, state, top_n=200, usd=100_000, max_bps=10, every=900, once=False, get=aget, delay=0.1):
    while True:
        try:
            tick = await get(FAPI + "/fapi/v1/ticker/24hr", "rest-binance")
            tick = [t for t in tick if t["symbol"].endswith("USDT") and "_" not in t["symbol"]]
            tick.sort(key=lambda t: -float(t["quoteVolume"]))
            passed = []
            for t in tick[:top_n]:
                sym = t["symbol"]
                try:
                    d = await get(f"{FAPI}/fapi/v1/depth?symbol={sym}&limit=100", "rest-binance")
                    b, s, ok = eval_depth(d, usd, max_bps)
                    sink.put([("scan", (c.now(), "binance", sym, float(t["quoteVolume"]), b, s, ok))])
                    if ok:
                        passed.append(sym)
                except Exception as e:
                    log.warning("scan %s: %s", sym, e)
                await asyncio.sleep(delay)
            state["tier1"] = passed
            for sym in passed:  # 15m candles, closed ones only
                try:
                    ks = await get(f"{FAPI}/fapi/v1/klines?symbol={sym}&interval=15m&limit=3", "rest-binance")
                    sink.put([norm_kline(sym, k) for k in ks if k[6] < c.now()])
                except Exception as e:
                    log.warning("klines %s: %s", sym, e)
                await asyncio.sleep(delay)
        except Exception as e:
            log.warning("tier_scan: %s", e)
        if once:
            return
        await asyncio.sleep(every)


# ---- Deribit options (BTC/ETH) ----
def expiry_ms(s):
    return int(datetime.strptime(s, "%d%b%y").replace(hour=8, tzinfo=timezone.utc).timestamp() * 1000)


def norm_deribit(js, ts):
    out = []
    for x in js.get("result", []):
        try:
            ccy, exp, strike, cp = x["instrument_name"].split("-")
            out.append(("options", (ts, "deribit", ccy, x["instrument_name"], c.fo(x.get("mark_iv")),
                                    c.fo(x.get("mark_price")), c.fo(x.get("open_interest")), c.fo(x.get("volume")),
                                    c.fo(x.get("underlying_price")), float(strike), expiry_ms(exp), cp)))
        except Exception:
            continue
    return out


async def poll_deribit(sink, ccys=("BTC", "ETH"), every=300, once=False, get=aget):
    while True:
        for ccy in ccys:
            try:
                js = await get(f"https://www.deribit.com/api/v2/public/get_book_summary_by_currency?currency={ccy}&kind=option", "rest-deribit")
                sink.put(norm_deribit(js, c.now()))
            except Exception as e:
                log.warning("deribit %s: %s", ccy, e)
        if once:
            return
        await asyncio.sleep(every)


# ---- long/short account ratio ----
async def poll_ls(sink, symbols, every=300, once=False, get=aget):
    while True:
        for s in symbols:
            try:
                for x in await get(f"{FAPI}/futures/data/globalLongShortAccountRatio?symbol={s}&period=5m&limit=1", "rest-binance"):
                    sink.put([("ls", (x["timestamp"], "binance", x["symbol"], float(x["longShortRatio"]),
                                      float(x["longAccount"]), float(x["shortAccount"])))])
            except Exception as e:
                log.warning("ls %s: %s", s, e)
        if once:
            return
        await asyncio.sleep(every)


def purge_now(sink):
    t = c.now()
    with sink.lock:  # sink.db is shared with the flusher thread
        for tbl, ms in RET_MS.items():
            sink.db.execute(f"DELETE FROM {tbl} WHERE ts<?", (t - ms,))
        sink.db.commit()


async def purge(sink, every=3600):
    while True:
        await asyncio.sleep(every)
        purge_now(sink)
