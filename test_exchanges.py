import asyncio, os, tempfile, time
import collector as c, exchanges as ex

NOW = c.now()
ex.CTVAL[("okx", "BTC-USDT-SWAP")] = 0.01
ex.CTVAL[("delta", "BTCUSD")] = 0.001


def rows(r, t): return [x[1] for x in r if x[0] == t]


def test_parsers():
    # binance
    r = ex.w_binance({"stream": "x", "data": {"e": "aggTrade", "a": 5, "p": "100", "q": "2", "T": NOW, "s": "BTCUSDT", "m": True}})
    assert r[0][1][6] == "sell" and r[0][1][4] == 100.0
    r = ex.w_binance({"data": {"e": "forceOrder", "o": {"s": "BTCUSDT", "S": "SELL", "q": "1", "z": "1", "p": "99", "ap": "98", "T": NOW}}})
    assert r[0][1][3] == "long" and r[0][1][6] == 98.0
    assert ex.p_bn_premium([{"symbol": "BTCUSDT", "time": NOW, "lastFundingRate": "0.0001", "markPrice": "1", "indexPrice": "1", "nextFundingTime": NOW}, {"symbol": "BTCUSDT_2412", "time": 1, "lastFundingRate": "", "markPrice": "1", "indexPrice": "1", "nextFundingTime": 1}], NOW)[0][1][3] == 0.0001
    # bybit
    r = ex.w_bybit({"topic": "publicTrade.BTCUSDT", "data": [{"T": NOW, "s": "BTCUSDT", "S": "Buy", "v": "0.1", "p": "100", "i": "a"}]})
    assert r[0][1][6] == "buy"
    r = ex.w_bybit({"topic": "allLiquidation.BTCUSDT", "data": [{"T": NOW, "s": "BTCUSDT", "S": "Buy", "v": "2", "p": "50"}]})
    assert r[0][1][3] == "long" and r[0][1][6] == 100.0
    r = ex.p_by_tickers({"result": {"list": [{"symbol": "BTCUSDT", "fundingRate": "0.0001", "openInterest": "10", "openInterestValue": "1000", "markPrice": "100", "indexPrice": "100", "nextFundingTime": "1"}, {"symbol": "BTC-27MAR26"}]}}, NOW)
    assert len(r) == 2
    r = ex.p_by_kl({"result": {"list": [[str(NOW - 1), "1", "2", "0.5", "1.5", "9", "10"], [str(NOW - 900_000 * 2), "1", "2", "0.5", "1.5", "9", "10"]]}}, NOW, "BTCUSDT")
    assert len(r) == 1  # first candle still open
    # okx contract scaling
    r = ex.w_okx({"arg": {"channel": "trades"}, "data": [{"instId": "BTC-USDT-SWAP", "tradeId": "1", "px": "100", "sz": "100", "side": "buy", "ts": str(NOW)}]})
    assert r[0][1][3] == "BTCUSDT" and abs(r[0][1][5] - 1.0) < 1e-9
    r = ex.w_okx({"arg": {"channel": "liquidation-orders"}, "data": [{"instId": "BTC-USDT-SWAP", "details": [{"side": "sell", "posSide": "long", "sz": "200", "bkPx": "10", "ts": str(NOW)}]}]})
    assert r[0][1][3] == "long" and abs(r[0][1][5] - 2.0) < 1e-9
    r = ex.p_ok_depth({"data": [{"bids": [["100", "100", "0", "1"]], "asks": [["100.1", "100", "0", "1"]]}]}, NOW, "BTC-USDT-SWAP")
    assert rows(r, "book")[0][5] == 100.0  # 100 contracts * 0.01 * 100px
    try:
        ex.p_ok_depth({"data": [{"bids": [["1", "1"]], "asks": [["2", "1"]]}]}, NOW, "XXX-USDT-SWAP"); assert False
    except KeyError: pass  # unknown contract size must NOT silently store wrong qty
    r = ex.p_ok_kl({"data": [[str(NOW - 2000000), "1", "2", "0", "1", "5", "0.05", "5", "1"], [str(NOW), "1", "2", "0", "1", "5", "0.05", "5", "0"]]}, NOW, "BTC-USDT-SWAP")
    assert len(r) == 1
    r = ex.p_ok_ls({"data": [[str(NOW), "1.5"]]}, NOW, "BTC")
    assert abs(r[0][1][4] - 0.6) < 1e-9
    r = ex.p_ok_ls({"data": [[str(NOW - 600_000), "0.8"], [str(NOW), "1.5"], [str(NOW - 300_000), "1.0"]]}, NOW, "BTC")
    assert len(r) == 1 and r[0][1][0] == NOW  # only the newest bucket is stored
    # bitget
    r = ex.w_bitget({"arg": {"instType": "USDT-FUTURES", "channel": "trade", "instId": "BTCUSDT"}, "data": [{"ts": str(NOW), "price": "100", "size": "1", "side": "sell", "tradeId": "9"}]})
    assert r[0][1][6] == "sell"
    assert len(ex.p_bg_tickers({"data": [{"symbol": "BTCUSDT", "ts": str(NOW), "fundingRate": "0.0001", "holdingAmount": "5", "markPrice": "1", "indexPrice": "1"}]}, NOW)) == 2
    # delta
    r = ex.w_delta({"type": "all_trades", "symbol": "BTCUSD", "price": "100", "size": 1000, "buyer_role": "taker", "timestamp": NOW * 1000})
    assert r[0][1][3] == "BTCUSDT" and abs(r[0][1][5] - 1.0) < 1e-9 and r[0][1][0] == NOW
    r = ex.p_dl_depth({"result": {"buy": [{"limit_price": "100", "size": 1000}], "sell": [{"limit_price": "100.1", "size": 1000}]}}, NOW, "BTCUSD")
    assert rows(r, "book")[0][5] == 100.0
    r = ex.p_dl_depth({"result": {"buy": [{"price": "100", "size": 1000}], "sell": [["100.1", 1000]]}}, NOW, "BTCUSD")
    assert rows(r, "book")[0][5] == 100.0  # alternate field names / list levels also parse
    assert ex.w_okx({"event": "subscribe", "arg": {"channel": "trades"}}) == []  # subscribe ack has no data
    # coindcx: dict book, list trades
    r = ex.p_dcx_depth({"bids": {"100": "1", "99.99": "2"}, "asks": {"100.1": "1"}}, NOW, "B-BTC_USDT")
    b = rows(r, "book")[0]
    assert b[2] == "BTCUSDT" and b[3] == 100.0 and b[4] == 100.1
    r = ex.p_dcx_trades([{"price": 100, "quantity": 2, "timestamp": NOW // 1000, "is_maker": False}], NOW, "B-BTC_USDT")
    assert r[0][1][0] == NOW // 1000 * 1000 and r[0][1][6] == "buy"
    assert ex.dcx_pair_list(["B-BTC_USDT", "B-ETH_INR", {"pair": "B-SOL_USDT"}, "KC-X_USDT"]) == ["B-BTC_USDT", "B-SOL_USDT"]
    # merged book across venues is comparable
    assert ex.book_row(NOW, "v", "BTCUSDT", [(100, 1), (90, 5)], [(100.01, 1)])[0][1][5] == 100


async def fake_get(url, name="rest"):
    u = url() if callable(url) else url
    if "active_instruments" in u: return ["B-BTC_USDT", "B-THIN_USDT"]
    if "exchange/ticker" in u: return [{"market": "USDTINR", "last_price": "100"}]  # Rs100/USDT -> Rs1L = $1000
    if "B-BTC_USDT-futures" in u: return {"bids": {"100": "100"}, "asks": {"100.01": "100"}}
    if "B-THIN_USDT-futures" in u: return {"bids": {"100": "1"}, "asks": {"100.5": "1"}}
    if "candlesticks" in u: return {"s": "ok", "data": [{"open": 1, "high": 2, "low": 0.5, "close": 1.5, "volume": 10, "time": NOW - 2_000_000}]}
    raise RuntimeError("unexpected " + u)


def test_tier_scan_dcx():
    s, st = c.Sink(os.path.join(tempfile.mkdtemp(), "x.db")), {}
    asyncio.run(ex.tier_scan_dcx(s, st, inr=100_000, once=True, get=fake_get, delay=0))
    s.flush()
    assert st["tier1"] == ["BTCUSDT"], st
    q = lambda sql: s.db.execute(sql).fetchall()
    assert q("select passed from scan where sym='THINUSDT'") == [(0,)]
    assert q("select count(*) from klines where venue='coindcx'")[0][0] == 1


def test_rest_feed_runner():
    feeds = ex.rest_feeds(["BTC"], {"binance", "bybit", "okx", "bitget", "delta", "coindcx"})
    assert len(feeds) >= 23 and all(callable(f["parse"]) for f in feeds)
    for f in feeds:
        u = f["url"]() if callable(f["url"]) else f["url"]
        assert u.startswith("https://") and "None" not in u, u
    assert len(ex.ws_feeds(["BTC", "ETH"], {"binance", "bybit", "okx", "bitget", "delta"})) == 5
    # parse error is counted, not stored
    async def bad(url, name="rest"): return {"unexpected": 1}
    s = c.Sink(":memory:")
    asyncio.run(ex.run_rest(s, feeds[1], {}, once=True, get=bad))
    assert c.STATS[feeds[1]["name"]]["errors"] == 1


def test_bulk_throttle():
    feeds = {f["name"]: f for f in ex.rest_feeds(["BTC"], {"bybit"})}
    f = feeds["rest-bybit-tickers"]
    assert f["bulk"] == {"BTCUSDT"}
    payload = {"result": {"list": [{"symbol": s, "fundingRate": "0.0001", "openInterest": "1", "openInterestValue": "1", "markPrice": "1", "indexPrice": "1", "nextFundingTime": "1"} for s in ("BTCUSDT", "XRPUSDT", "SOLUSDT")]}}
    async def g(url, name="rest"): return payload
    s, st = c.Sink(":memory:"), {}
    asyncio.run(ex.run_rest(s, f, st, once=True, get=g)); s.flush()
    assert s.db.execute("select count(distinct sym) from funding").fetchone()[0] == 3   # first poll = full
    asyncio.run(ex.run_rest(s, f, st, once=True, get=g)); s.flush()
    assert s.db.execute("select count(*) from funding where sym='XRPUSDT'").fetchone()[0] == 1  # 2nd poll: only wishlist
    assert s.db.execute("select count(*) from funding where sym='BTCUSDT'").fetchone()[0] == 2


def test_flow_aggregation():
    s = c.Sink(":memory:", whale_usd=50_000, flow_bps=3)
    T = NOW - 5 * 60_000  # closed minute
    tr = lambda i, p, q, side, tid: ("trades", (T + i, "v", "perp", "BTCUSDT", p, q, side, tid))
    s.put([tr(1, 100000.0, 0.1, "buy", "a"), tr(2, 100010.0, 0.2, "buy", "b"), tr(3, 100000.0, 0.3, "sell", "c"),
           tr(4, 100000.0, 1.0, "buy", "w"), tr(5, 100000.0, 0.1, "buy", "a")])  # "a" repeated = duplicate poll
    s.flush()
    q = lambda sql: s.db.execute(sql).fetchall()
    assert q("select tid from trades") == [("w",)]                     # only the whale kept individually
    f = q("select sum(buy_qty), sum(sell_qty), sum(n_buy), sum(n_sell) from flow")[0]
    assert abs(f[0] - 1.3) < 1e-9 and abs(f[1] - 0.3) < 1e-9 and f[2:] == (3, 1), f   # small + whale all in flow, dup ignored
    s.put([tr(6, 100000.0, 0.5, "buy", "late")]); s.flush()           # late trade for a closed minute adds, not replaces
    assert abs(q("select sum(buy_qty) from flow")[0][0] - 1.8) < 1e-9
    assert c.nice_step(100000, 3) == 20 and c.nice_step(2500, 3) == 0.5 and abs(c.nice_step(0.5, 3) - 0.0001) < 1e-12


if __name__ == "__main__":
    test_parsers(); test_tier_scan_dcx(); test_rest_feed_runner(); test_bulk_throttle(); test_flow_aggregation()
    print("exchanges OK")
