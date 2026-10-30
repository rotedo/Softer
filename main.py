"""FlowMap backend: aggregates free public futures data from many exchanges.
Run: uvicorn main:app --host 0.0.0.0 --port $PORT
Env: COINS=BTC,ETH  EXCHANGES=binance,okx,...  RETENTION_MIN=360
"""
import asyncio, json, math, os, time
from collections import defaultdict, deque
from contextlib import asynccontextmanager

import httpx
import websockets
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

COINS = [c.strip().upper() for c in os.getenv("COINS", "BTC,ETH").split(",") if c.strip()]
EXLIST = [e.strip().lower() for e in os.getenv(
    "EXCHANGES", "binance,okx,bybit,bitget,gate,mexc,delta,coindcx").split(",") if e.strip()]
RETENTION = int(os.getenv("RETENTION_MIN", "360"))
# our name -> ccxt id (perpetual futures). delta + coindcx are native adapters below.
CCXT_IDS = {"binance": "binanceusdm", "okx": "okx", "bybit": "bybit", "bitget": "bitget",
            "gate": "gate", "mexc": "mexc", "kucoin": "kucoinfutures", "bingx": "bingx",
            "htx": "htx", "hyperliquid": "hyperliquid", "deribit": "deribit",
            "kraken": "krakenfutures", "bitmex": "bitmex", "phemex": "phemex"}
NAMES = {"binance": "Binance", "okx": "OKX", "bybit": "Bybit", "bitget": "Bitget", "gate": "Gate",
         "mexc": "MEXC", "kucoin": "KuCoin", "bingx": "BingX", "htx": "HTX", "hyperliquid": "Hyperliquid",
         "deribit": "Deribit", "kraken": "Kraken", "bitmex": "BitMEX", "phemex": "Phemex",
         "delta": "Delta Exchange", "coindcx": "CoinDCX"}
EXLIST = [e for e in EXLIST if e in CCXT_IDS or e in ("delta", "coindcx")]
# finest price bin we store per coin (display ticks are multiples of this)
FINE = {"BTC": 1.0, "ETH": 0.05, "SOL": 0.01, "XRP": 0.0001, "BNB": 0.1, "DOGE": 0.00001,
        "HYPE": 0.01, "NEAR": 0.001, "ZEC": 0.1}

BARS = defaultdict(lambda: defaultdict(dict))  # BARS[coin][ex][minute_ts] = bar
LIQS = {c: deque(maxlen=20000) for c in COINS}  # (ts, price, usd, side, ex)
LAST = {}                                       # (coin, ex) -> (ts, price)
EXOBJ, MKT = {}, defaultdict(dict)              # ccxt objects + chosen markets
STATUS = {e: {"name": NAMES[e], "status": "starting", "trades": 0, "last": 0, "error": "", "symbols": {}}
          for e in EXLIST}


def nice(x):
    if x <= 0:
        return 1.0
    e = 10 ** math.floor(math.log10(x))
    for m in (1, 2, 2.5, 5, 10):
        if x <= m * e * 1.0000001:
            return round(m * e, 12)
    return round(10 * e, 12)


def ingest(coin, ex, ts, px, qty, is_buy):
    """Add one trade. qty must be in BASE coin units (e.g. BTC)."""
    if not (px > 0 and qty > 0) or coin not in COINS:
        return
    fine = FINE.get(coin) or FINE.setdefault(coin, nice(px * 0.00002))
    mt = int(ts // 60 * 60)
    bars = BARS[coin][ex]
    b = bars.get(mt)
    if b is None:
        b = bars[mt] = {"o": px, "h": px, "l": px, "c": px, "to": ts, "tc": ts,
                        "buy": 0.0, "sell": 0.0, "lv": {}}
        if len(bars) > RETENTION + 5:
            cut = mt - RETENTION * 60
            for k in [k for k in bars if k < cut]:
                del bars[k]
    if ts < b["to"]:
        b["o"], b["to"] = px, ts
    if ts >= b["tc"]:
        b["c"], b["tc"] = px, ts
    b["h"], b["l"] = max(b["h"], px), min(b["l"], px)
    b["buy" if is_buy else "sell"] += qty
    i = int(px // fine)
    lv = b["lv"].get(i)
    if lv is None:
        lv = b["lv"][i] = [0.0, 0.0]
    lv[0 if is_buy else 1] += qty
    LAST[(coin, ex)] = (ts, px)
    st = STATUS[ex]
    st["trades"] += 1
    st["last"] = ts


# ---------------------------------------------------------------- exchange streams
def pick_market(ex, coin):
    rank = {"USDT": 0, "USDC": 1, "USD": 2}
    best = None
    for m in ex.markets.values():
        if m.get("base") != coin or not m.get("swap") or m.get("active") is False:
            continue
        if m.get("quote") not in rank:
            continue
        r = rank[m["quote"]] + (0 if m.get("linear") else 0.5)
        if best is None or r < best[0]:
            best = (r, m)
    return best[1] if best else None


async def watch_coin(name, ex, coin, m):
    cs = m.get("contractSize") or 1
    inv = bool(m.get("inverse"))
    while True:
        for t in await ex.watch_trades(m["symbol"]):
            px, amt, ts = t.get("price"), t.get("amount"), t.get("timestamp")
            if not px or not amt or not ts:
                continue
            qty = amt * cs / px if inv else amt * cs
            ingest(coin, name, ts / 1000, px, qty, t.get("side") == "buy")


async def stream_ccxt(name):
    st = STATUS[name]
    while True:
        ex = None
        try:
            import ccxt.pro as ccxtpro
            ex = getattr(ccxtpro, CCXT_IDS[name])({"enableRateLimit": True, "newUpdates": True})
            await ex.load_markets()
            picks = {c: pick_market(ex, c) for c in COINS}
            picks = {c: m for c, m in picks.items() if m}
            if not picks:
                raise RuntimeError("no matching perp markets")
            EXOBJ[name] = ex
            MKT[name] = picks
            st.update(status="connected", error="", symbols={c: m["symbol"] for c, m in picks.items()})
            async with asyncio.TaskGroup() as tg:
                for c, m in picks.items():
                    tg.create_task(watch_coin(name, ex, c, m))
        except asyncio.CancelledError:
            raise
        except BaseException as e:  # noqa
            err = e.exceptions[0] if hasattr(e, "exceptions") and e.exceptions else e
            st.update(status="error", error=f"{type(err).__name__}: {str(err)[:160]}")
        finally:
            if ex is not None:
                try:
                    await ex.close()
                except Exception:
                    pass
        await asyncio.sleep(20)


DELTA_REST, DELTA_WS = "https://api.india.delta.exchange", "wss://socket.india.delta.exchange"


async def stream_delta():
    st = STATUS["delta"]
    while True:
        try:
            async with httpx.AsyncClient(timeout=15) as c:
                r = (await c.get(f"{DELTA_REST}/v2/products", params={
                    "contract_types": "perpetual_futures", "states": "live", "page_size": 500})).json()
            prods = {p["symbol"]: p for p in r.get("result", [])}
            want = {}
            for coin in COINS:
                for sym in (f"{coin}USDT", f"{coin}USD"):
                    if sym in prods:
                        want[sym] = (coin, float(prods[sym].get("contract_value") or 1))
                        break
            if not want:
                raise RuntimeError("no matching products")
            st.update(status="connected", error="", symbols={v[0]: k for k, v in want.items()})
            async with websockets.connect(DELTA_WS, ping_interval=20) as ws:
                await ws.send(json.dumps({"type": "subscribe", "payload": {
                    "channels": [{"name": "all_trades", "symbols": list(want)}]}}))
                async for raw in ws:
                    d = json.loads(raw)
                    if d.get("type") != "all_trades" or d.get("symbol") not in want:
                        continue
                    coin, cv = want[d["symbol"]]
                    ts = float(d.get("timestamp") or time.time() * 1e6)
                    ts = ts / 1e6 if ts > 1e14 else ts / 1e3 if ts > 1e11 else ts
                    ingest(coin, "delta", ts, float(d["price"]), float(d["size"]) * cv,
                           d.get("buyer_role") == "taker")
        except asyncio.CancelledError:
            raise
        except Exception as e:
            st.update(status="error", error=f"{type(e).__name__}: {str(e)[:160]}")
        await asyncio.sleep(15)


async def stream_coindcx():
    """CoinDCX futures: REST polling of public trade history (their socket needs old socket.io 2.x)."""
    st = STATUS["coindcx"]
    seen = {c: deque(maxlen=500) for c in COINS}
    async with httpx.AsyncClient(timeout=10) as cl:
        while True:
            try:
                for coin in COINS:
                    r = await cl.get("https://public.coindcx.com/market_data/trade_history",
                                     params={"pair": f"B-{coin}_USDT", "limit": 50})
                    for t in reversed(r.json()):
                        key = (t.get("timestamp"), t.get("price"), t.get("quantity"))
                        if key in seen[coin]:
                            continue
                        seen[coin].append(key)
                        ts = float(t["timestamp"])
                        ts = ts / 1e3 if ts > 1e11 else ts
                        # is_maker=True is treated as "buyer was maker" => aggressive SELL
                        ingest(coin, "coindcx", ts, float(t["price"]), float(t["quantity"]), not t.get("is_maker"))
                    st["symbols"][coin] = f"B-{coin}_USDT"
                st.update(status="connected", error="")
            except asyncio.CancelledError:
                raise
            except Exception as e:
                st.update(status="error", error=f"{type(e).__name__}: {str(e)[:160]}")
            await asyncio.sleep(2)


async def liq_binance():
    url = "wss://fstream.binance.com/ws/!forceOrder@arr"
    while True:
        try:
            async with websockets.connect(url, ping_interval=20) as ws:
                async for raw in ws:
                    o = json.loads(raw).get("o", {})
                    s = o.get("s", "")
                    coin = s[:-4] if s.endswith("USDT") else ""
                    if coin in LIQS:
                        px, q = float(o["ap"]), float(o["z"])
                        # SELL order = a LONG was liquidated
                        LIQS[coin].append((o["T"] / 1000, px, px * q, "long" if o["S"] == "SELL" else "short", "binance"))
        except asyncio.CancelledError:
            raise
        except Exception:
            await asyncio.sleep(5)


async def liq_bybit():
    url = "wss://stream.bybit.com/v5/public/linear"
    while True:
        try:
            async with websockets.connect(url, ping_interval=20) as ws:
                await ws.send(json.dumps({"op": "subscribe", "args": [f"allLiquidation.{c}USDT" for c in COINS]}))
                async for raw in ws:
                    d = json.loads(raw)
                    if not str(d.get("topic", "")).startswith("allLiquidation"):
                        continue
                    for x in d.get("data", []):
                        coin = x["s"][:-4]
                        if coin in LIQS:
                            px, q = float(x["p"]), float(x["v"])
                            # S=Buy means a LONG position was liquidated
                            LIQS[coin].append((int(x["T"]) / 1000, px, px * q, "long" if x["S"] == "Buy" else "short", "bybit"))
        except asyncio.CancelledError:
            raise
        except Exception:
            await asyncio.sleep(5)


@asynccontextmanager
async def lifespan(app):
    tasks = [asyncio.create_task(liq_binance()), asyncio.create_task(liq_bybit())]
    for e in EXLIST:
        fn = {"delta": stream_delta, "coindcx": stream_coindcx}.get(e)
        tasks.append(asyncio.create_task(fn() if fn else stream_ccxt(e)))
    yield
    for t in tasks:
        t.cancel()


app = FastAPI(title="FlowMap", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


# ---------------------------------------------------------------- API
def names_for(coin, ex):
    have = BARS.get(coin, {})
    return [n for n in EXLIST if n in have] if ex == "all" else ([ex] if ex in have else [])


@app.get("/")
def index():
    return FileResponse(os.path.join(os.path.dirname(__file__), "index.html"))


@app.get("/api/health")
def health():
    now = time.time()
    return {"coins": COINS, "exchanges": {k: {**v, "age_s": round(now - v["last"], 1) if v["last"] else None}
                                           for k, v in STATUS.items()}}


@app.get("/api/meta")
def meta():
    return {"coins": COINS, "retention": RETENTION,
            "exchanges": [{"id": k, "name": v["name"], "status": v["status"], "trades": v["trades"]}
                          for k, v in STATUS.items()]}


@app.get("/api/footprint")
def footprint(coin: str = "BTC", ex: str = "all", tf: int = 5, n: int = 24, tick: float = 0, lv: int = 1):
    """Candles + per-price buy/sell volume (footprint) + delta, merged across exchanges."""
    coin = coin.upper()
    names = names_for(coin, ex)
    if not names:
        return {"tick": 0, "candles": [], "exchanges": []}
    fine = FINE.get(coin, 1.0)
    bucket = max(1, tf) * 60
    ref = max((LAST[(coin, nm)] for nm in names if (coin, nm) in LAST), key=lambda x: x[0])[1]
    tk = tick or nice(ref * 0.0002)
    step = max(1, round(tk / fine))
    C = {}
    for nm in names:
        for mt, b in BARS[coin][nm].items():
            k = int(mt // bucket * bucket)
            c = C.get(k)
            if c is None:
                c = C[k] = {"t": k, "o": b["o"], "to": b["to"], "h": b["h"], "l": b["l"], "c": b["c"],
                            "tc": b["tc"], "buy": 0.0, "sell": 0.0, "lv": {}}
            else:
                if b["to"] < c["to"]:
                    c["o"], c["to"] = b["o"], b["to"]
                if b["tc"] >= c["tc"]:
                    c["c"], c["tc"] = b["c"], b["tc"]
                c["h"], c["l"] = max(c["h"], b["h"]), min(c["l"], b["l"])
            c["buy"] += b["buy"]
            c["sell"] += b["sell"]
            if lv:
                for i, (bu, se) in b["lv"].items():
                    key = (i // step) * step
                    cell = c["lv"].setdefault(key, [0.0, 0.0])
                    cell[0] += bu
                    cell[1] += se
    out = []
    for k in sorted(C)[-n:]:
        c = C[k]
        out.append({"t": k, "o": c["o"], "h": c["h"], "l": c["l"], "c": c["c"], "buy": c["buy"],
                    "sell": c["sell"], "delta": c["buy"] - c["sell"],
                    "lv": [[round(i * fine, 10), v[0], v[1]] for i, v in sorted(c["lv"].items(), reverse=True)]})
    return {"tick": round(step * fine, 10), "candles": out, "exchanges": names}


@app.get("/api/liqs")
def liqs(coin: str = "BTC", ex: str = "all", minutes: int = 360, tf: int = 5, tick: float = 0):
    since = time.time() - minutes * 60
    rows = [r for r in LIQS.get(coin.upper(), []) if r[0] >= since and (ex == "all" or r[4] == ex)]
    if not rows:
        return {"cells": [], "levels": [], "tick": 0, "long": 0, "short": 0}
    tk = tick or nice(rows[-1][1] * 0.0005)
    cells = defaultdict(lambda: {"long": 0.0, "short": 0.0})
    lev = defaultdict(lambda: {"long": 0.0, "short": 0.0})
    for ts, px, usd, side, _ in rows:
        pb = round(math.floor(px / tk) * tk, 10)
        cells[(int(ts // (tf * 60) * tf * 60), pb)][side] += usd
        lev[pb][side] += usd
    return {"tick": tk,
            "cells": [{"t": t, "p": p, **v} for (t, p), v in sorted(cells.items())],
            "levels": [{"p": p, **v} for p, v in sorted(lev.items(), reverse=True)],
            "long": sum(r[2] for r in rows if r[3] == "long"), "short": sum(r[2] for r in rows if r[3] == "short")}


_bk, _dv = {}, {}


async def get_book(name, coin):
    c = _bk.get((name, coin))
    if c and time.time() - c[0] < 2:
        return c[1]
    m = MKT[name][coin]
    ob = await EXOBJ[name].fetch_order_book(m["symbol"], 50)
    cs, inv = m.get("contractSize") or 1, m.get("inverse")
    conv = lambda x: (x[0], x[1] * cs / x[0] if inv else x[1] * cs)
    res = {"asks": [conv(x) for x in ob["asks"]], "bids": [conv(x) for x in ob["bids"]]}
    _bk[(name, coin)] = (time.time(), res)
    return res


@app.get("/api/book")
async def book(coin: str = "BTC", ex: str = "all", tick: float = 0):
    coin = coin.upper()
    names = [n for n in (EXLIST if ex == "all" else [ex]) if n in EXOBJ and coin in MKT.get(n, {})]
    res = await asyncio.gather(*[get_book(n, coin) for n in names], return_exceptions=True)
    good = [(n, r) for n, r in zip(names, res) if isinstance(r, dict) and r["asks"] and r["bids"]]
    if not good:
        return {"asks": [], "bids": [], "exchanges": [], "mid": 0, "tick": 0}
    mid = sum((r["bids"][0][0] + r["asks"][0][0]) / 2 for _, r in good) / len(good)
    tk = tick or nice(mid * 0.00005)
    A, B = defaultdict(float), defaultdict(float)
    for _, r in good:
        for p, q in r["asks"]:
            A[round(math.ceil(p / tk) * tk, 10)] += q
        for p, q in r["bids"]:
            B[round(math.floor(p / tk) * tk, 10)] += q

    def side(d, rev):
        acc, out = 0.0, []
        for p, q in sorted(d.items(), reverse=rev)[:40]:
            acc += q
            out.append([p, q, acc])
        return out
    return {"asks": side(A, False), "bids": side(B, True), "mid": mid, "tick": tk, "exchanges": [n for n, _ in good]}


async def get_derivs(name, coin):
    c = _dv.get((name, coin))
    if c and time.time() - c[0] < 30:
        return c[1]
    ex, m = EXOBJ[name], MKT[name][coin]
    out = {}
    try:
        out["funding"] = (await ex.fetch_funding_rate(m["symbol"])).get("fundingRate")
    except Exception as e:
        out["funding_err"] = type(e).__name__
    try:
        oi = await ex.fetch_open_interest(m["symbol"])
        v = oi.get("openInterestValue")
        if v is None and oi.get("openInterestAmount") is not None and (coin, name) in LAST:
            v = oi["openInterestAmount"] * (m.get("contractSize") or 1) * LAST[(coin, name)][1]
        out["oi_usd"] = v
    except Exception as e:
        out["oi_err"] = type(e).__name__
    _dv[(name, coin)] = (time.time(), out)
    return out


@app.get("/api/derivs")
async def derivs(coin: str = "BTC", ex: str = "all"):
    coin = coin.upper()
    names = [n for n in (EXLIST if ex == "all" else [ex]) if n in EXOBJ and coin in MKT.get(n, {})]
    res = await asyncio.gather(*[get_derivs(n, coin) for n in names])
    rows = [{"ex": n, "name": NAMES[n], **r} for n, r in zip(names, res)]
    oi = sum(r.get("oi_usd") or 0 for r in rows)
    w = [(r["funding"], r.get("oi_usd") or 0) for r in rows if r.get("funding") is not None]
    tw = sum(x[1] for x in w)
    fr = sum(f * o for f, o in w) / tw if tw else (sum(f for f, _ in w) / len(w) if w else None)
    return {"rows": rows, "oi_total": oi, "funding_avg": fr}
