"""Weekly archive: old collector data -> ZIP of CSV files -> your phone -> only then deleted from the server.

File format: Parquet (one file per table, zstd compressed, typed columns) when `pyarrow` is installed (it is in requirements.txt);
read it with pandas.read_parquet("flow.parquet") or DuckDB. If pyarrow is missing the archive falls back to a ZIP of CSV files
so nothing is ever lost because of a missing package. Force the fallback with ARCHIVE_FORMAT=csv.

What happens, every ARCHIVE_EVERY_D days (default 7):
  1. every row older than ARCHIVE_KEEP_H hours (default 72h, the window the live chart / liquidation model needs) of the bulky tables
     (flow, trades, book, liqs, funding, oi, options) is written to archive/orderflow_<stamp>_<table>.parquet (+ a small manifest .json)
  2. delivery: Telegram only. Bot token + chat id are entered in the app (Settings screen) or in config.py; the file lands in your chat.
  3. ONLY after delivery is confirmed (Telegram said ok) the exported rows are deleted
     and the zip on the server is removed. Nothing is deleted before that. If delivery never happens, the old retention in
     extras.RET_MS (raised to 14 days while archiving is on) is the last-resort safety net.
Kept on the server, never archived: klines (15m candles, tiny), ls, scan.
"""
import csv, io, json, logging, os, re, shutil, sqlite3, threading, time, uuid, urllib.request, zipfile
import collector as c, config, store

log = logging.getLogger("archive")
TABLES = ["flow", "trades", "book", "liqs", "funding", "oi", "options"]
PART_BYTES = 100 * 1024 * 1024   # CSV fallback: uncompressed bytes per zip part (compresses 4x+ -> under Telegram's 50 MB bot limit)
PQ_ROWS = 2_000_000              # Parquet: rows per file (a big table is split so each file stays small enough for Telegram)
TG_MAX = 49 * 1024 * 1024
SINK = None                      # main.py sets this so deletes share the collector's writer lock
_LOCK = threading.Lock()


def enabled():
    return os.environ.get("ARCHIVE", "1") != "0"


def every_ms():
    return float(os.environ.get("ARCHIVE_EVERY_D", "7")) * 86_400_000


def keep_ms():
    return float(os.environ.get("ARCHIVE_KEEP_H", "72")) * 3_600_000


def folder():
    d = os.environ.get("ARCHIVE_DIR") or os.path.join(os.path.dirname(os.path.abspath(os.environ.get("DB_PATH", "orderflow.db"))), "archive")
    os.makedirs(d, exist_ok=True)
    return d


def tg_cfg():
    """(token, chat id): the Settings screen first, config.py / env as fallback"""
    try:
        t = store.telegram_get(True)
        if t["token"] and t["chat_id"]:
            return t["token"], t["chat_id"]
    except Exception:
        pass
    return config.get("TELEGRAM_BOT_TOKEN"), config.get("TELEGRAM_CHAT_ID")


def tg_message(text):
    """Send a plain message to the saved Telegram chat. -> {'ok': bool, 'error': str}"""
    import urllib.error, urllib.parse
    token, chat = tg_cfg()
    if not (token and chat):
        return {"ok": False, "error": "token or chat id is not saved yet"}
    req = urllib.request.Request(f"https://api.telegram.org/bot{token}/sendMessage", urllib.parse.urlencode({"chat_id": chat, "text": text}).encode())
    try:
        return {"ok": bool(json.load(urllib.request.urlopen(req, timeout=20)).get("ok")), "error": ""}
    except urllib.error.HTTPError as e:
        try:
            return {"ok": False, "error": json.loads(e.read()).get("description", f"HTTP {e.code}")}
        except Exception:
            return {"ok": False, "error": f"HTTP {e.code}"}
    except Exception as e:
        return {"ok": False, "error": f"cannot reach Telegram ({type(e).__name__})"}


def raise_retention(ret):
    """While archiving is on, never let the old purge delete bulky rows before a weekly archive could take them."""
    for t in TABLES:
        ret[t] = max(ret.get(t, 0), 14 * 864e5)


# ---------------------------------------------------------------- manifests
def _mpath(i):
    return os.path.join(folder(), f"orderflow_{i}.json")


def manifests():
    out = []
    for f in sorted(os.listdir(folder())):
        if re.fullmatch(r"orderflow_[0-9-]+\.json", f):
            try:
                out.append(json.load(open(os.path.join(folder(), f))))
            except (OSError, ValueError):
                pass
    return out


def _save(m):
    with open(_mpath(m["id"]), "w") as f:
        json.dump(m, f)


def _start_marker():
    p = os.path.join(folder(), ".start")
    if not os.path.exists(p):
        with open(p, "w") as f:
            f.write(str(c.now()))
    return int(open(p).read() or 0)


def next_due():
    ms = manifests()
    last = max([m["created"] for m in ms] + [_start_marker()])
    return last + every_ms()


# ---------------------------------------------------------------- export
class _Parts:
    """Writes CSV rows into zip parts of at most PART_BYTES uncompressed bytes."""

    def __init__(self, stamp):
        self.stamp, self.k, self.size, self.zf, self.files = stamp, 0, 0, None, []
        self.cur, self.csvn = None, None

    def _open(self):
        self.k += 1
        name = f"orderflow_{self.stamp}_part{self.k}.zip"
        path = os.path.join(folder(), name)
        self.zf = zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED, compresslevel=6)
        self.files.append(path)
        self.size = 0

    def begin(self, table, cols):
        self.table, self.cols, self.n = table, cols, 0
        self._start_csv()

    def _start_csv(self):
        if self.zf is None or self.size >= PART_BYTES:
            self.close_csv()
            if self.zf:
                self.zf.close()
            self._open()
        self.close_csv()
        self.n += 1
        self.cur = self.zf.open(f"{self.table}{'' if self.n == 1 else '_' + str(self.n)}.csv", "w")
        self._w(self.cols)

    def _w(self, row):
        b = io.StringIO()
        csv.writer(b).writerow(row)
        data = b.getvalue().encode()
        self.cur.write(data)
        self.size += len(data)

    def row(self, r):
        if self.size >= PART_BYTES:
            self._start_csv()
        self._w(r)

    def close_csv(self):
        if self.cur:
            self.cur.close()
            self.cur = None

    def finish(self):
        self.close_csv()
        if self.zf:
            self.zf.close()
        return self.files


def _pq():
    try:
        import pyarrow as pa, pyarrow.parquet as pq
        return pa, pq
    except Exception:
        return None


def ensure_pyarrow():
    """Parquet needs pyarrow. The server only runs `pip install -r requirements.txt` when the instance is first built, so if the package is
    missing install it once, in the background, into the same environment (disable with ARCHIVE_AUTOINSTALL=0). CSV-zip is used until it is there."""
    if _pq() or os.environ.get("ARCHIVE_AUTOINSTALL", "1") == "0" or os.environ.get("ARCHIVE_FORMAT", "").lower() == "csv":
        return
    import importlib, subprocess, sys
    try:
        log.info("pyarrow missing: installing it once (Parquet archives)")
        r = subprocess.run([sys.executable, "-m", "pip", "install", "-q", "pyarrow>=15.0"], capture_output=True, text=True, timeout=900)
        importlib.invalidate_caches()
        log.info("pyarrow install %s", "done" if r.returncode == 0 and _pq() else "failed: " + (r.stderr or "")[-200:])
    except Exception as e:
        log.warning("pyarrow install failed: %s", e)


def fmt():
    """'parquet' if pyarrow is importable (and not disabled), else 'csv' (zip of CSV files)."""
    return "parquet" if os.environ.get("ARCHIVE_FORMAT", "parquet").lower() != "csv" and _pq() else "csv"


def _write_parquet(con, t, cutoff, mx, stamp):
    """One table -> one or more typed, zstd-compressed .parquet files. Returns the file paths."""
    pa, pq = _pq()
    kinds = {"INTEGER": pa.int64(), "REAL": pa.float64(), "TEXT": pa.string()}
    fields = [(r[1], kinds.get((r[2] or "TEXT").upper(), pa.string())) for r in con.execute(f"PRAGMA table_info({t})")]
    schema = pa.schema(fields)
    files, k, w, n = [], 0, None, 0
    cur = con.execute(f"SELECT * FROM {t} WHERE ts<? AND rowid<=? ORDER BY ts", (cutoff, mx))
    try:
        while True:
            chunk = cur.fetchmany(50000)
            if not chunk:
                break
            if w is None or n >= PQ_ROWS:
                if w:
                    w.close()
                k += 1
                path = os.path.join(folder(), f"orderflow_{stamp}_{t}{'' if k == 1 else '_' + str(k)}.parquet")
                w = pq.ParquetWriter(path, schema, compression="zstd")
                files.append(path)
                n = 0
            cols = list(zip(*chunk))
            w.write_table(pa.Table.from_arrays([pa.array(col, type=f[1]) for col, f in zip(cols, fields)], schema=schema))
            n += len(chunk)
    finally:
        if w:
            w.close()
    return files


def create(now=None):
    """Export everything older than keep window. Returns the manifest (or None if nothing to export)."""
    now = now or c.now()
    cutoff = now - keep_ms()
    stamp = time.strftime("%Y%m%d-%H%M", time.gmtime(now / 1000))
    db = os.environ.get("DB_PATH", "orderflow.db")
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=30)
    parts, rows, bound, tmin, pq_files = _Parts(stamp), {}, {}, {}, []
    use_pq = fmt() == "parquet"
    try:
        for t in TABLES:
            mx = con.execute(f"SELECT max(rowid) FROM {t}").fetchone()[0] or 0
            cols = [r[1] for r in con.execute(f"PRAGMA table_info({t})")]
            n = con.execute(f"SELECT count(*), min(ts) FROM {t} WHERE ts<? AND rowid<=?", (cutoff, mx)).fetchone()
            if not n[0]:
                continue
            if use_pq:
                pq_files += _write_parquet(con, t, cutoff, mx, stamp)
            else:
                parts.begin(t, cols)
                cur = con.execute(f"SELECT * FROM {t} WHERE ts<? AND rowid<=? ORDER BY ts", (cutoff, mx))
                while True:
                    chunk = cur.fetchmany(20000)
                    if not chunk:
                        break
                    for r in chunk:
                        parts.row(r)
            rows[t], bound[t], tmin[t] = n[0], mx, n[1]
        files = pq_files if use_pq else parts.finish()
    finally:
        con.close()
    if not rows:
        for f in parts.files + pq_files:
            os.path.exists(f) and os.remove(f)
        return None
    m = {"id": stamp, "created": now, "cutoff": cutoff, "rows": rows, "max_rowid": bound, "from_ts": min(tmin.values()), "format": "parquet" if use_pq else "csv",
         "parts": [{"file": os.path.basename(f), "bytes": os.path.getsize(f)} for f in files], "delivered": None, "deleted": False}
    _save(m)
    return m


# ---------------------------------------------------------------- delivery
def _tg_send(token, chat, path, caption):
    b = uuid.uuid4().hex
    with open(path, "rb") as f:
        data = f.read()

    def field(n, v):
        return f'--{b}\r\nContent-Disposition: form-data; name="{n}"\r\n\r\n{v}\r\n'.encode()
    body = (field("chat_id", chat) + field("caption", caption) +
            f'--{b}\r\nContent-Disposition: form-data; name="document"; filename="{os.path.basename(path)}"\r\nContent-Type: application/octet-stream\r\n\r\n'.encode() +
            data + f"\r\n--{b}--\r\n".encode())
    req = urllib.request.Request(f"https://api.telegram.org/bot{token}/sendDocument", body, {"Content-Type": f"multipart/form-data; boundary={b}"})
    return bool(json.load(urllib.request.urlopen(req, timeout=300)).get("ok"))


def deliver_telegram(m):
    token, chat = tg_cfg()
    if not (token and chat):
        return False
    try:
        for i, p in enumerate(m["parts"], 1):
            path = os.path.join(folder(), p["file"])
            if p["bytes"] > TG_MAX:
                log.warning("archive part %s is %.0f MB - over Telegram's limit, use Download", p["file"], p["bytes"] / 1e6)
                return False
            day = time.strftime("%Y-%m-%d", time.gmtime(m["from_ts"] / 1000))
            if not _tg_send(token, chat, path, f"Orderflow archive {day} -> {time.strftime('%Y-%m-%d', time.gmtime(m['cutoff'] / 1000))} (part {i}/{len(m['parts'])})"):
                return False
        return True
    except Exception as e:
        log.warning("telegram delivery failed: %s", e)
        return False


# ---------------------------------------------------------------- delete exported rows (only after delivery)
def _exec_delete(sql, args):
    if SINK is not None:
        with SINK.lock:
            cur = SINK.db.execute(sql, args)
            SINK.db.commit()
            return cur.rowcount
    con = sqlite3.connect(os.environ.get("DB_PATH", "orderflow.db"), timeout=30)
    try:
        cur = con.execute(sql, args)
        con.commit()
        return cur.rowcount
    finally:
        con.close()


def purge_exported(m, batch=20000):
    for t, mx in m["max_rowid"].items():
        while True:
            n = _exec_delete(f"DELETE FROM {t} WHERE rowid IN (SELECT rowid FROM {t} WHERE ts<? AND rowid<=? LIMIT ?)", (m["cutoff"], mx, batch))
            if n < batch:
                break
            time.sleep(0.05)
    try:
        _exec_delete("PRAGMA wal_checkpoint(TRUNCATE)", ())
    except Exception:
        pass
    for p in m["parts"]:
        f = os.path.join(folder(), p["file"])
        if os.path.exists(f):
            os.remove(f)
    m["deleted"] = True
    _save(m)


def _finish(m, via):
    m["delivered"] = {"via": via, "at": c.now()}
    _save(m)
    purge_exported(m)


# ---------------------------------------------------------------- orchestration
def pending():
    return next((m for m in manifests() if not m["deleted"]), None)


def run_once(force=False):
    """Create (if due) and try to deliver. Safe to call any time; one run at a time."""
    if not _LOCK.acquire(blocking=False):
        return {"status": "busy"}
    try:
        m = pending()
        if m is None:
            if not (force or c.now() >= next_due()):
                return {"status": "not due", "next_due": next_due()}
            m = create()
            if m is None:
                with open(os.path.join(folder(), ".start"), "w") as f:  # nothing old enough yet: look again after one period
                    f.write(str(c.now()))
                return {"status": "nothing to archive"}
        if not m["delivered"] and deliver_telegram(m):
            _finish(m, "telegram")
            return {"status": "delivered via telegram, server rows deleted", "id": m["id"]}
        return {"status": "waiting for download" if not tg_cfg()[0] else "telegram failed - use Download", "id": m["id"]}
    finally:
        _LOCK.release()


def status():
    ms = manifests()
    tok, chat = tg_cfg()
    db = os.environ.get("DB_PATH", "orderflow.db")
    return {"enabled": enabled(), "format": fmt(), "telegram": bool(tok and chat), "every_days": every_ms() / 864e5, "keep_hours": keep_ms() / 3.6e6,
            "next_due": next_due() if enabled() else None, "db_mb": round(os.path.getsize(db) / 1e6, 1) if os.path.exists(db) else None,
            "archives": [{"id": m["id"], "created": m["created"], "from_ts": m["from_ts"], "cutoff": m["cutoff"], "rows": sum(m["rows"].values()), "tables": m["rows"],
                          "files": [] if m["deleted"] else m["parts"], "delivered": m["delivered"], "deleted": m["deleted"]} for m in reversed(ms)][:20],
            "last_sent": max([m["delivered"]["at"] for m in ms if m.get("delivered")] or [0]) or None}


def read_part(name):
    """Bytes of one archive file, only if it belongs to a manifest (no path tricks)."""
    for m in manifests():
        if not m["deleted"] and any(p["file"] == name for p in m["parts"]):
            with open(os.path.join(folder(), name), "rb") as f:
                return f.read()
    raise ValueError("no such archive file")


def ack(i):
    """User confirms the files are saved on the phone -> delete exported rows + server copy."""
    m = next((x for x in manifests() if x["id"] == str(i) and not x["deleted"]), None)
    if not m:
        raise ValueError("archive not found (already cleaned?)")
    _finish(m, "download")
    return {"ok": True, "deleted_rows": sum(m["rows"].values())}


async def loop(sink=None):
    import asyncio
    global SINK
    SINK = sink or SINK
    try:
        await asyncio.get_running_loop().run_in_executor(None, ensure_pyarrow)
    except Exception:
        log.exception("pyarrow check failed")
    while True:
        if enabled():
            try:
                await asyncio.get_running_loop().run_in_executor(None, run_once)
            except Exception:
                log.exception("archive run failed")
        await asyncio.sleep(3600)
