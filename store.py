"""app.db: everything the user creates (journal, drawings, settings, agents, watchlist). Separate from orderflow.db."""
import json, os, re, sqlite3, threading, time

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


# secrets entered in the Settings screen (stored in app.db on the server, never returned in full) -----------
ROLES = ("chat", "backup", "off")


def _mk(k):
    return ("\u2022\u2022\u2022\u2022" + k[-4:]) if k and len(k) > 4 else ("\u2022\u2022\u2022\u2022" if k else "")


def gemini_keys(with_key=False):
    out = []
    for k in kv_get("gemini_keys", []) or []:
        d = {"id": k["id"], "name": k.get("name", ""), "work": k.get("work", ""), "role": k.get("role", "chat"), "masked": _mk(k.get("key", "")), "has_key": bool(k.get("key")), "provider": k.get("provider") or (__import__("llm").detect(k.get("key", "")) if k.get("key") else ""), "model": k.get("model", ""), "base": k.get("base", "")}
        if with_key:
            d["key"] = k.get("key", "")
        out.append(d)
    return out


def _base_ok(b, provider):
    b = str(b or "").strip().rstrip("/")
    if provider == "custom" and not re.match(r"https://[\w.-]+(:\d+)?(/[\w./-]*)?$", b):
        raise ValueError("Custom API: base URL must start with https:// (example: https://api.example.com/v1)")
    return b if provider == "custom" else ""


def gemini_key_save(d):
    ks = kv_get("gemini_keys", []) or []
    key = str(d.get("key") or "").strip()
    role = d.get("role") if d.get("role") in ROLES else "chat"
    name, work = str(d.get("name") or "").strip()[:40] or "AI key", str(d.get("work") or "").strip()[:300]
    if d.get("id"):
        old = next((k for k in ks if k["id"] == int(d["id"])), None)
        if not old:
            raise ValueError("key not found")
        if key:
            if len(key) < 20:
                raise ValueError("that does not look like an API key")
            old["key"] = key
            old.pop("provider", None)
        old.update(name=name, work=work, role=role, model=str(d.get("model") or "").strip()[:80])
        if d.get("provider"):
            old["provider"] = d["provider"]
        old["base"] = _base_ok(d.get("base"), old.get("provider"))
        i = old["id"]
    else:
        if len(key) < 20:
            raise ValueError("paste the full API key")
        i = max([k["id"] for k in ks] + [0]) + 1
        ks.append({"id": i, "name": name, "work": work, "role": role, "key": key, "model": str(d.get("model") or "").strip()[:80], "provider": d.get("provider") or "", "base": _base_ok(d.get("base"), d.get("provider"))})
    kv_set("gemini_keys", ks)
    return i


def gemini_key_del(i):
    kv_set("gemini_keys", [k for k in (kv_get("gemini_keys", []) or []) if k["id"] != int(i)])


def telegram_get(with_secret=False):
    t = kv_get("telegram", {}) or {}
    tok = t.get("token", "")
    d = {"chat_id": t.get("chat_id", ""), "masked": _mk(tok), "has_token": bool(tok)}
    if with_secret:
        d["token"] = tok
    return d


def telegram_save(d):
    t = kv_get("telegram", {}) or {}
    tok = str(d.get("token") or "").strip()
    if tok:
        if ":" not in tok or len(tok) < 30:
            raise ValueError("that does not look like a bot token (from @BotFather, like 123456:ABC...)")
        t["token"] = tok
    chat = str(d.get("chat_id") or "").strip()
    if chat and not re.fullmatch(r"-?\d{5,20}|@[A-Za-z0-9_]{4,}", chat):
        raise ValueError("chat id must be a number like 123456789 (or -100... for a group)")
    t["chat_id"] = chat
    kv_set("telegram", t)


# scripts (Pine-style screener scripts) --------------------------------
def scripts_get():
    return kv_get("scripts", None)


def scripts_set(v):
    kv_set("scripts", v)
  
