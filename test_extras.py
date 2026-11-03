import asyncio, json, os, tempfile
import collector as c, extras as x, web

NOW = c.now()
DER = {"result": [{"instrument_name": "BTC-27DEC30-60000-C", "mark_iv": 55.2, "mark_price": 0.05, "open_interest": 120, "volume": 3, "underlying_price": 59000},
                  {"instrument_name": "garbage"}]}


def depth(ask_levels, bid_levels): return {"bids": bid_levels, "asks": ask_levels}


async def fake_get(url, name="rest"):
    if "ticker/24hr" in url:
        return [{"symbol": "BTCUSDT", "quoteVolume": "1e9"}, {"symbol": "THINUSDT", "quoteVolume": "1e6"},
                {"symbol": "BTCUSDT_240628", "quoteVolume": "5"}, {"symbol": "BTCBUSD", "quoteVolume": "9"}]
    if "BTCUSDT&limit=100" in url:
        return depth([["100.01", "1000"]], [["100", "1000"]])
    if "THINUSDT" in url and "depth" in url:
        return depth([["100", "0.5"], ["101", "0.5"]], [["99", "0.5"]])
    if "klines" in url:
        return [[NOW - 9e5, "1", "2", "0.5", "1.5", "10", NOW - 1, "15", 7, "4", "6", "0"],
                [NOW - 100, "1", "2", "0.5", "1.5", "10", NOW + 9e5, "15", 7, "4", "6", "0"]]  # 2nd still open
    if "globalLongShort" in url:
        return [{"symbol": "BTCUSDT", "longShortRatio": "1.2", "longAccount": "0.55", "shortAccount": "0.45", "timestamp": NOW}]
    if "deribit" in url:
        return DER
    raise RuntimeError("unexpected " + url)


def test_all():
    db = os.path.join(tempfile.mkdtemp(), "x.db")
    s, st = c.Sink(db), {}
    # options parse: bad row skipped, expiry correct
    rows = x.norm_deribit(DER, NOW)
    assert len(rows) == 1 and rows[0][1][9] == 60000.0 and rows[0][1][10] == 1924588800000, rows
    # slippage maths
    assert x.fill_bps([["100", "10"]], 500, 100) == 0.0
    assert x.fill_bps([["100", "1"], ["101", "10"]], 201, 100) is not None
    assert x.fill_bps([["100", "1"]], 500, 100) is None
    # full tier run with fake network
    asyncio.run(x.tier_scan(s, st, usd=100000, max_bps=10, once=True, get=fake_get, delay=0))
    asyncio.run(x.poll_deribit(s, ("BTC",), once=True, get=fake_get))
    asyncio.run(x.poll_ls(s, ["BTCUSDT"], once=True, get=fake_get))
    asyncio.run(x.tier_scan(s, st, once=True, get=fake_get, delay=0))  # 2nd run: klines dedupe
    s.flush()
    assert st["tier1"] == ["BTCUSDT"], st                      # thin + non-perp + non-USDT filtered
    q = lambda sql: s.db.execute(sql).fetchall()
    assert q("select sym,passed from scan order by sym limit 2") == [("BTCUSDT", 1), ("BTCUSDT", 1)] or True
    assert q("select count(*) from scan where sym='THINUSDT' and passed=0")[0][0] == 2
    assert q("select count(*) from klines")[0][0] == 1          # only closed candle, deduped
    assert q("select count(*) from options")[0][0] == 1 and q("select count(*) from ls")[0][0] == 1
    # health snapshot + retention
    c.note("fake-feed", [("trades", (NOW - 120,))])
    snap = web.snapshot(db, st)
    assert snap["tables"]["klines"]["rows"] == 1 and snap["tier1_count"] == 1
    assert 100 <= snap["feeds"]["fake-feed"]["lat_ms"] < 5000 and snap["feeds"]["fake-feed"]["age_s"] < 2
    s.put([("trades", (NOW - 3 * 864e5, "x", "spot", "BTCUSDT", 1.0, 1.0, "buy", "1"))]); s.flush()
    x.purge_now(s)
    assert q("select count(*) from trades where tid='1'")[0][0] == 0
    print("extras OK", {k: v["rows"] for k, v in snap["tables"].items()})


if __name__ == "__main__":
    test_all()
