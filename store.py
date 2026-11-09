"""app.db: everything the user creates (journal, drawings, settings, agents, watchlist). Separate from orderflow.db."""
import json, os, sqlite3, threading, time

APP_DB = os.environ.get("APP_DB") or os.path.join(os.path.dirname(os.path.abspath(os.environ.get("DB_PATH", "orderflow.db"))), "app.db")
_L = threading.Lock()
_C = None


def db():
    global _C
    if _C is None:
        _C = sqlite3.connect(APP_DB, check_same_thread=False)
        _C.row_factory = sqlite3.Row
        _C.execute("PRAGMA journal_mode=WAL")
        for s in ("CREATE TABLE IF NOT EXISTS kv(k TEXT PRIMARY KEY, v TEXT)",
                  "CREATE TABLE IF NOT EXISTS journal(id INTEGER PRIMARY KEY, ts INTEGER, data TEXT)",
                  "CREATE TABLE IF NOT EXISTS agents(id INTEGER PRIMARY KEY, name TEXT, work TEXT, key TEXT, main INTEGER DEFAULT 0, x REAL DEFAULT 20, y REAL DEFAULT 20)",
                  "CREATE TABLE IF NOT EXISTS links(a INTEGER, b INTEGER, PRIMARY KEY(a,b))"):
            _C.execute(s)
        _C.commit()
    return _C


def reset_for_tests(path):
    global _C, APP_DB
    APP_DB, _C = path, None


def kv_get(k, default=None):
    with _L:
        r = db().execute("SELECT v FROM kv WHERE k=?", (k,)).fetchone()
    return json.loads(r["v"]) if r else default


def kv_set(k, v):
    with _L:
        db().execute("INSERT OR REPLACE INTO kv VALUES(?,?)", (k, json.dumps(v)))
        db().commit()


# journal -----------------------------------------------------------
def journal_list():
    with _L:
        return [dict(json.loads(r["data"]), id=r["id"], ts=r["ts"]) for r in db().execute("SELECT * FROM journal ORDER BY ts DESC LIMIT 500")]


def journal_add(d):
    d = {k: v for k, v in d.items() if k not in ("id", "ts")}
    with _L:
        cur = db().execute("INSERT INTO journal(ts,data) VALUES(?,?)", (int(time.time() * 1000), json.dumps(d)))
        db().commit()
        return cur.lastrowid


def journal_del(i):
    with _L:
        db().execute("DELETE FROM journal WHERE id=?", (int(i),))
        db().commit()


# agents (keys never returned) ---------------------------------------
def _mask(k):
    return ("…" + k[-4:]) if k else ""


def agents_list(with_key=False):
    with _L:
        rows = db().execute("SELECT * FROM agents ORDER BY id").fetchall()
        links = [[r["a"], r["b"]] for r in db().execute("SELECT a,b FROM links")]
    out = [{"id": r["id"], "name": r["name"], "work": r["work"], "main": bool(r["main"]), "x": r["x"], "y": r["y"],
            "key": r["key"] if with_key else _mask(r["key"]), "has_key": bool(r["key"])} for r in rows]
    return {"agents": out, "links": links}


def agent_save(d):
    with _L:
        c = db()
        if d.get("id"):
            old = c.execute("SELECT key FROM agents WHERE id=?", (d["id"],)).fetchone()
            key = d["key"] if d.get("key") and not str(d["key"]).startswith("…") else (old["key"] if old else "")
            c.execute("UPDATE agents SET name=?,work=?,key=?,main=?,x=?,y=? WHERE id=?",
                      (d.get("name", "agent")[:40], d.get("work", "")[:500], key, int(bool(d.get("main"))), d.get("x", 20), d.get("y", 20), d["id"]))
            i = d["id"]
        else:
            i = c.execute("INSERT INTO agents(name,work,key,main,x,y) VALUES(?,?,?,?,?,?)",
                          (d.get("name", "agent")[:40], d.get("work", "")[:500], d.get("key", ""), int(bool(d.get("main"))), d.get("x", 20), d.get("y", 20))).lastrowid
        c.commit()
    return i


def agent_del(i):
    with _L:
        db().execute("DELETE FROM agents WHERE id=?", (int(i),))
        db().execute("DELETE FROM links WHERE a=? OR b=?", (int(i), int(i)))
        db().commit()


def link(a, b, on=True):
    with _L:
        if on:
            db().execute("INSERT OR IGNORE INTO links VALUES(?,?)", (int(a), int(b)))
        else:
            db().execute("DELETE FROM links WHERE (a=? AND b=?) OR (a=? AND b=?)", (int(a), int(b), int(b), int(a)))
        db().commit()


def linked(a, b):
    with _L:
        return bool(db().execute("SELECT 1 FROM links WHERE (a=? AND b=?) OR (a=? AND b=?)", (a, b, b, a)).fetchone())
