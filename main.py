"""Entry point.  python main.py          -> run collector + health dashboard
                python main.py probe    -> hit every endpoint once, print what parsed / what failed, exit"""
import asyncio, logging, os, shutil, sys
import collector as c, config, extras as x, exchanges as ex, web, jobs, archive, screener, https_proxy
try:
    import pump_live
except Exception:  # the old app must still start if the pump files are broken
    pump_live = None

ALL = "binance,bybit,okx,bitget,delta,coindcx,deribit"
# Order-flow collection (BTC/ETH ticks, books, funding...) is OFF. The new pump system does not store anything.
# To switch the old collector back on, set the environment variable COLLECT=1 on the server.
COLLECT = os.environ.get("COLLECT", "0") == "1"


def purge_old_flow(db):
    """Delete the old order-flow data: orderflow.db (+ its -wal/-shm files) and the archive folder.
    NEVER touches app.db (your journal, settings, keys, watchlist). Safe to run on every start."""
    here = os.path.dirname(os.path.abspath(db))
    app_db = os.path.abspath(os.environ.get("APP_DB") or os.path.join(here, "app.db"))
    freed = 0
    for f in (db, db + "-wal", db + "-shm", db + "-journal"):
        p = os.path.abspath(f)
        if p != app_db and os.path.isfile(p):
            try:
                freed += os.path.getsize(p)
                os.remove(p)
            except OSError as e:
                logging.warning("could not delete %s: %s", p, e)
    arch = os.path.abspath(os.environ.get("ARCHIVE_DIR") or os.path.join(here, "archive"))
    if os.path.basename(arch) == "archive" and os.path.isdir(arch):  # only a folder literally named "archive"
        for root, _, files in os.walk(arch):
            for n in files:
                try:
                    freed += os.path.getsize(os.path.join(root, n))
                except OSError:
                    pass
        shutil.rmtree(arch, ignore_errors=True)
    if freed:
        logging.info("old order-flow data deleted: %.1f MB freed", freed / 1e6)
    return freed


def cfg():
    wish = config.watchlist()  # config.py WATCHLIST + env WISHLIST
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
    db, port = os.environ.get("DB_PATH", "orderflow.db"), int(os.environ.get("PORT", "8000"))
    if not COLLECT:
        purge_old_flow(db)  # before the sink opens the file: old data goes, an empty tiny db is recreated
    sink, state = c.Sink(db, whale_usd=float(os.environ.get("WHALE_USD", "50000")), flow_bps=float(os.environ.get("FLOW_BPS", "3"))), {"live": os.environ.get("LIVE", "0") == "1"}
    web.start_server(db, state, port)
    https_proxy.autostart()  # free HTTPS link, only if you switched it on in Settings
    if COLLECT:
        try:
            await ex.load_ctvals()  # contract sizes must exist before the first parse
        except Exception as e:
            logging.warning("ctval preload failed: %s", e)
    tasks = [sink.flusher(), jobs.loop(), screener.loop()]
    if pump_live:
        tasks.append(pump_live.loop())  # live pump scanner: runs 24x7, scans only while switched ON on the /pump page
    if COLLECT:  # old order-flow collector (OFF by default)
        tasks += [x.purge(sink), ex.ctval_loop()]
        if archive.enabled():  # weekly zip -> phone -> delete (see archive.py); old purge becomes only a safety net
            archive.raise_retention(x.RET_MS)
            tasks.append(archive.loop(sink))
        tasks += [ex.run_rest(sink, f, state) for f in ex.rest_feeds(wish, venues)]
        tasks += [c.ws_run(sink, **w) for w in ex.ws_feeds(wish, venues)]
        if "coindcx" in venues:
            tasks.append(ex.tier_scan_dcx(sink, state, inr=float(os.environ.get("DCX_INR", "1000000")), max_bps=float(os.environ.get("DCX_MAX_BPS", "10"))))
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
