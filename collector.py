"""Core: clock, feed stats, SQLite sink (unified schema), REST helper, WebSocket runner."""
import asyncio, json, logging, sqlite3, threading, time, urllib.request

log = logging.getLogger("collector")
STATS = {}  # feed name -> health/latency stats (read by web.py)
UA = "Mozilla/5.0 (compatible; orderflow-collector/1.0)"


def now():
    return int(time.time() * 1000)


def fo(x):
    """float-or-None"""
    try:
        return None if x in (None, "") else float(x)
    except (TypeError, ValueError):
        return None


def stat(name, kind="ws"):
    return STATS.setdefault(name, {"kind": kind, "last_rx": None, "lat_ms": None, "msgs": 0,
                                   "reconnects": 0, "errors": 0, "last_err": None})


def note(name, rows=None, lat=None, kind=None):
    """Mark a message received. lat = explicit latency ms (REST round trip) or derived from the first trade ts."""
    s = stat(name, kind or ("rest" if name.startswith("rest") else "ws"))
    t = now()
    s["last_rx"] = t
    s["msgs"] += 1
    if lat is None and rows:
        for tbl, r in rows:
            if tbl == "trades":
                lat = max(0, t - int(r[0]))
                break
    if lat is not None:
        s["lat_ms"] = int(lat)


# One unified schema for every venue. sym is canonical (BASE+USDT, e.g. BTCUSDT); qty is always in BASE coin units.
SCHEMA = [
    "CREATE TABLE IF NOT EXISTS trades(ts INTEGER, venue TEXT, market TEXT, sym TEXT, price REAL, qty REAL, side TEXT, tid TEXT, UNIQUE(venue,sym,tid))",
    "CREATE TABLE IF NOT EXISTS book(ts INTEGER, venue TEXT, sym TEXT, bid REAL, ask REAL, bid_depth REAL, ask_depth REAL, imb REAL)",
    "CREATE TABLE IF NOT EXISTS liqs(ts INTEGER, venue TEXT, sym TEXT, side TEXT, price REAL, qty REAL, notional REAL)",
    "CREATE TABLE IF NOT EXISTS funding(ts INTEGER, venue TEXT, sym TEXT, rate REAL, mark REAL, index_px REAL, next_ts INTEGER)",
    "CREATE TABLE IF NOT EXISTS oi(ts INTEGER, venue TEXT, sym TEXT, qty REAL, usd REAL)",
    "CREATE TABLE IF NOT EXISTS options(ts INTEGER, venue TEXT, ccy TEXT, name TEXT, iv REAL, mark REAL, oi REAL, vol REAL, und REAL, strike REAL, expiry INTEGER, cp TEXT)",
    "CREATE TABLE IF NOT EXISTS ls(ts INTEGER, venue TEXT, sym TEXT, ratio REAL, long_pct REAL, short_pct REAL)",
    "CREATE TABLE IF NOT EXISTS scan(ts INTEGER, venue TEXT, sym TEXT, qvol REAL, buy_bps REAL, sell_bps REAL, passed INTEGER)",
    "CREATE TABLE IF NOT EXISTS klines(ts INTEGER, venue TEXT, sym TEXT, o REAL, h REAL, l REAL, c REAL, v REAL, qv REAL, n INTEGER, tbv REAL, PRIMARY KEY(ts,venue,sym))",
]
TABLES = ["trades", "book", "liqs", "funding", "oi", "options", "ls", "scan", "klines"]


class Sink:
    def __init__(self, path):
        self.db = sqlite3.connect(path, check_same_thread=False, timeout=5)
        self.lock = threading.RLock()
        self.buf = []
        with self.lock:
            self.db.execute("PRAGMA journal_mode=WAL")
            self.db.execute("PRAGMA synchronous=NORMAL")
            for ddl in SCHEMA:
                self.db.execute(ddl)
            for t in TABLES:
                self.db.execute(f"CREATE INDEX IF NOT EXISTS ix_{t}_ts ON {t}(ts)")
            self.db.commit()

    def put(self, rows):
        with self.lock:
            self.buf.extend(rows)
            big = len(self.buf) > 5000
        if big:
            self.flush()

    def flush(self):
        with self.lock:
            buf, self.buf = self.buf, []
            by = {}
            for tbl, r in buf:
                by.setdefault(tbl, []).append(r)
            for tbl, rs in by.items():
                try:
                    self.db.executemany(f"INSERT OR IGNORE INTO {tbl} VALUES ({','.join('?' * len(rs[0]))})", rs)
                except Exception as e:
                    stat("sink", "rest")["errors"] += 1
                    stat("sink", "rest")["last_err"] = f"{tbl}: {e}"[:80]
            self.db.commit()

    async def flusher(self, every=1.0):
        loop = asyncio.get_running_loop()
        while True:
            await asyncio.sleep(every)
            await loop.run_in_executor(None, self.flush)


async def aget(url, name="rest"):
    """GET json; records round-trip latency under `name` (url may be a callable for time-dependent urls)."""
    u = url() if callable(url) else url

    def _get():
        req = urllib.request.Request(u, headers={"User-Agent": UA, "Accept": "application/json"})
        return json.load(urllib.request.urlopen(req, timeout=15))
    t = time.time()
    try:
        d = await asyncio.get_running_loop().run_in_executor(None, _get)
        note(name, lat=int((time.time() - t) * 1000))
        return d
    except Exception as e:
        s = stat(name, "rest")
        s["errors"] += 1
        s["last_err"] = str(e)[:80]
        raise


async def _app_ping(ws, msg, every):
    while True:
        await asyncio.sleep(every)
        await ws.send(msg if isinstance(msg, str) else json.dumps(msg))


async def ws_run(sink, name, url, subs, parse, app_ping=None, ping_every=20):
    """Reconnecting websocket feed. parse(msg_dict) -> [(table,row)]. app_ping = text/dict for venues needing app-level pings."""
    import websockets
    st = stat(name, "ws")
    backoff = 1
    while True:
        pinger = None
        try:
            async with websockets.connect(url, ping_interval=20, max_size=2 ** 23) as ws:
                for m in subs:
                    await ws.send(m if isinstance(m, str) else json.dumps(m))
                if app_ping:
                    pinger = asyncio.create_task(_app_ping(ws, app_ping, ping_every))
                backoff = 1
                async for raw in ws:
                    if raw in ("pong", b"pong"):
                        continue
                    try:
                        rows = parse(json.loads(raw))
                    except Exception as e:
                        st["errors"] += 1
                        st["last_err"] = f"parse: {e}"[:80]
                        continue
                    if rows:
                        sink.put(rows)
                    note(name, rows)
        except Exception as e:
            st["errors"] += 1
            st["last_err"] = str(e)[:80]
        finally:
            if pinger:
                pinger.cancel()
        st["reconnects"] += 1
        await asyncio.sleep(min(backoff, 30))
        backoff *= 2
