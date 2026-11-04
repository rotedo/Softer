"""Entry point.  python main.py          -> run collector + health dashboard
                python main.py probe    -> hit every endpoint once, print what parsed / what failed, exit"""
import asyncio, logging, os, sys
import collector as c, extras as x, exchanges as ex, web

ALL = "binance,bybit,okx,bitget,delta,coindcx,deribit"


def cfg():
    wish = [b.strip().upper() for b in os.environ.get("WISHLIST", "BTC,ETH").split(",") if b.strip()]
    venues = {v.strip() for v in os.environ.get("VENUES", ALL).split(",")}
    return wish, venues


async def guard(coro):
    """one crashing job must never take the others down"""
    name = getattr(coro, "__qualname__", "task")
    try:
        await coro
    except Exception as e:
        logging.exception("job crashed: %s", name)
        s = c.stat(f"crash-{name}", "rest")
        s["errors"] += 1
        s["last_err"] = f"{type(e).__name__}: {e}"[:80]


async def main():
    wish, venues = cfg()
    db, port = os.environ.get("DB_PATH", "orderflow.db"), int(os.environ.get("PORT", "10000"))
    sink, state = c.Sink(db, whale_usd=float(os.environ.get("WHALE_USD", "50000")), flow_bps=float(os.environ.get("FLOW_BPS", "3"))), {"live": os.environ.get("LIVE", "0") == "1"}
    web.start_server(db, state, port)
    tasks = [sink.flusher(), x.purge(sink), ex.ctval_loop()]
    tasks += [ex.run_rest(sink, f, state) for f in ex.rest_feeds(wish, venues)]
    tasks += [c.ws_run(sink, **w) for w in ex.ws_feeds(wish, venues)]
    if "coindcx" in venues:
        tasks.append(ex.tier_scan_dcx(sink, state, inr=float(os.environ.get("DCX_INR", "100000")), max_bps=float(os.environ.get("DCX_MAX_BPS", "10"))))
    if "deribit" in venues:
        c.stat("rest-deribit", "rest")["max_age_s"] = 700
        tasks.append(x.poll_deribit(sink))
    logging.info("wishlist=%s venues=%s live=%s", wish, sorted(venues), state["live"])
    await asyncio.gather(*[guard(t) for t in tasks])


async def probe():
    wish, venues = cfg()
    sink, state = c.Sink(":memory:"), {}
    try:
        await ex.load_ctvals()
    except Exception as e:
        print("ctvals FAILED:", e)
    print(f"contract sizes loaded: {len(ex.CTVAL)}")
    await asyncio.gather(*[ex.run_rest(sink, f, state, once=True) for f in ex.rest_feeds(wish, venues)])
    await ex.tier_scan_dcx(sink, state, once=True, delay=0.05) if "coindcx" in venues else None
    for w in ex.ws_feeds(wish, venues):
        try:
            await asyncio.wait_for(c.ws_run(sink, **w), 12)
        except asyncio.TimeoutError:
            pass
    sink.flush()
    print("\n=== feeds (OK = data parsed) ===")
    for k, s in sorted(c.STATS.items()):
        ok = s["msgs"] > 0 and s["errors"] == 0
        print(f"{'OK ' if ok else 'BAD'} {k:32} lat={s['lat_ms']}ms msgs={s['msgs']} err={s['errors']} {s.get('last_err') or ''}")
    print("\n=== rows per table / venue ===")
    for t in c.TABLES:
        r = sink.db.execute(f"SELECT venue, count(*) FROM {t} GROUP BY venue").fetchall()
        print(t, dict(r))
    print("tier1 (CoinDCX, passes Rs 1L slippage):", state.get("tier1"))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    asyncio.run(probe() if "probe" in sys.argv else main())
