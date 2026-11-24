"""The only entry point web.py calls:  handle(method, path, headers, body, client_ip) -> (status, content_type, bytes, extra_headers)"""
import json, os, subprocess
from urllib.parse import urlparse, parse_qs
import os, re, sys, threading, config, vision, aggregator as a, agents, analysis, archive, auth, backtester, jobs, news, scanner, screener, store

HEALTH = lambda: {}  # web.py replaces this with its snapshot()
J = "application/json"


def _r(code, obj, hdr=None):
    return code, J, json.dumps(obj, default=str).encode(), hdr or {}


def _cookie(headers):
    for part in (headers.get("Cookie") or headers.get("cookie") or "").split(";"):
        k, _, v = part.strip().partition("=")
        if k == "ft":
            return v
    return ""


def _q(qs, k, d=None, cast=str):
    try:
        return cast(qs[k][0]) if k in qs else d
    except Exception:
        return d


def _ask_fn():
    return (lambda p: agents.gemini(agents.keys(), "Reply exactly as asked.", p)) if agents.keys() else None


def _sys_health():
    h = HEALTH() or {}
    try:
        h["restarts"] = int(subprocess.run(["systemctl", "show", "orderflow", "-p", "NRestarts", "--value"], capture_output=True, text=True, timeout=3).stdout.strip() or 0)
    except Exception:
        h["restarts"] = None
    try:
        h["db_mb"] = round(os.path.getsize(a.DB_PATH) / 1e6, 1)
    except OSError:
        h["db_mb"] = None
    h["gemini"] = bool(agents.keys())
    h["gemini_keys"] = len(agents.keys())
    h["ai_keys"] = len(agents.keys())
    return h


def handle(method, path, headers, body, client_ip="?"):
    u = urlparse(path)
    p, qs = u.path.rstrip("/"), parse_qs(u.query)
    try:
        data = json.loads(body) if body else {}
    except Exception:
        return _r(400, {"error": "bad json"})
    try:
        if p == "/api/ping":
            return _r(200, {"ok": True, "auth_configured": auth.configured()})
        if p == "/api/login" and method == "POST":
            if not auth.configured():
                return _r(503, {"error": "ADMIN_PASSWORD not configured on the server"})
            if auth.limited(client_ip):
                return _r(429, {"error": "too many attempts, wait 15 minutes"})
            t = auth.login(data.get("password", ""), client_ip)
            if not t:
                return _r(401, {"error": "wrong password"})
            return _r(200, {"ok": True}, {"Set-Cookie": f"ft={t}; HttpOnly; SameSite=Strict; Path=/; Max-Age={auth.TTL}"})
        if p == "/api/logout":
            return _r(200, {"ok": True}, {"Set-Cookie": "ft=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0"})
        if not auth.configured():
            return _r(503, {"error": "ADMIN_PASSWORD not configured on the server"})
        if not auth.valid(_cookie(headers)):
            return _r(401, {"error": "login required"})
        sym = _q(qs, "sym", "BTCUSDT").upper()
        if p == "/api/chart":  # candles + footprint + GEX / liquidation / volume / reversal levels, one call
            return _r(200, analysis.chart(sym, _q(qs, "tf", "15m"), min(_q(qs, "n", 200, int), 600)))
        if p == "/api/coins":
            tm = {t["sym"]: t["tier"] for t in jobs.CACHE.get("tiers") or []} or None
            return _r(200, analysis.coins(tm))
        if p == "/api/symbols":
            return _r(200, analysis.symbols(_q(qs, "q", "")))
        if p == "/api/derivs":
            return _r(200, analysis.derivs(sym))
        if p == "/api/transcribe" and method == "POST":
            import llm
            return _r(200, {"text": llm.transcribe(agents.keys(), str(data.get("audio", "")), str(data.get("mime") or "audio/webm"))})
        if p == "/api/chat" and method == "POST":
            import llm
            text = str(data.get("text", ""))
            if data.get("web"):
                ctx = llm.web_context(agents.keys(), text)
                text = text + ("\n\n[Web search results, use them for news and outside facts:]\n" + ctx if ctx else "\n\n[Web search was not available: add a Gemini key in Settings]")
            return _r(200, agents.chat(data.get("syms") or str(data.get("sym", "BTCUSDT")).upper(), text, data.get("history"), str(data.get("tf", "15m"))))
        if p == "/api/keys":
            if method == "POST":
                return _r(200, {"id": store.gemini_key_save(data)})
            if method == "DELETE":
                store.gemini_key_del(_q(qs, "id", 0, int))
                return _r(200, {"ok": True})
            return _r(200, {"keys": store.gemini_keys(), "model": agents.MODEL()})
        if p == "/api/keys/test" and method == "POST":
            k = next((x for x in store.gemini_keys(True) if x["id"] == int(data.get("id", 0))), None)
            if not k:
                raise ValueError("key not found")
            return _r(200, agents.test_key({"provider": k.get("provider") or "", "key": k["key"], "model": k.get("model", ""), "base": k.get("base", "")} if k.get("provider") else k["key"]))
        if p == "/api/scripts":
            if method == "POST":
                return _r(200, {"id": screener.save_script(data)})
            if method == "DELETE":
                screener.delete_script(_q(qs, "id", 0, int))
                return _r(200, {"ok": True})
            return _r(200, {"scripts": screener.scripts(), "cfg": screener.cfg(), "last": screener.LAST, "alerts": screener.recent()})
        if p == "/api/scripts/test" and method == "POST":
            return _r(200, screener.test_script(str(data.get("code", "")), str(data.get("sym", "BTCUSDT")).upper(), str(data.get("tf", "15m"))))
        if p == "/api/scripts/ai" and method == "POST":
            return _r(200, screener.ai_script(data.get("prompt"), data.get("name"), str(data.get("tf") or "15m")))
        if p == "/api/screener/run" and method == "POST":
            return _r(200, {"new": screener.run_once()})
        if p == "/api/screener/cfg" and method == "POST":
            sp = data.get("spike") or {}
            store.kv_set("screener_cfg", {"every_min": max(1, min(int(data.get("every_min", 5)), 120)), "ai": bool(data.get("ai")),
                                          "universe": "tier2" if data.get("universe") == "tier2" else "tier1",
                                          "spike": {"on": bool(sp.get("on", True)), "pct": max(0.5, min(float(sp.get("pct", 3)), 50)),
                                                    "mins": max(1, min(int(sp.get("mins", 5)), 15)), "cooldown": max(1, min(int(sp.get("cooldown", 10)), 120))}})
            return _r(200, screener.cfg())
        if p == "/api/dashboard":
            t = jobs.CACHE.get("tiers") or a.tiers()
            return _r(200, {"tiers": t, "alerts": screener.recent()[:10], "scripts_on": sum(1 for x in screener.scripts() if x.get("on")), "ai_keys": len(agents.keys()), "last": screener.LAST})
        if p == "/api/telegram":
            if method == "POST":
                store.telegram_save(data)
            st = archive.status()
            return _r(200, store.telegram_get() | {"archive_every_days": st["every_days"], "next_due": st["next_due"], "last_sent": st["last_sent"], "db_mb": st["db_mb"], "waiting": any(not x["deleted"] and not x["delivered"] for x in st["archives"])})
        if p == "/api/telegram/test" and method == "POST":
            return _r(200, archive.tg_message("Hi \U0001F44B Orderflow Terminal is connected. Your weekly data archives will arrive in this chat."))
        if p == "/api/archive":
            return _r(200, archive.status())
        if p == "/api/archive/run" and method == "POST":
            return _r(200, archive.run_once(force=True))
        if p == "/api/archive/ack" and method == "POST":
            return _r(200, archive.ack(data.get("id", "")))
        if p == "/api/archive/get":
            name = _q(qs, "name", "")
            return 200, "application/zip" if name.endswith(".zip") else "application/octet-stream", archive.read_part(name), {"Content-Disposition": f'attachment; filename="{name}"'}
        if p == "/api/bundle":
            return _r(200, a.bundle(sym, _q(qs, "tf", "15m"), min(_q(qs, "n", 200, int), 1000)))
        if p == "/api/liq":
            return _r(200, a.liq_zones(sym, _q(qs, "hours", 72, int)))
        if p == "/api/gex":
            return _r(200, a.gex(_q(qs, "ccy", "BTC").upper()))
        if p == "/api/book":
            return _r(200, a.book(sym))
        if p == "/api/tape":
            return _r(200, a.tape(sym))
        if p == "/api/futures":
            return _r(200, a.futures(sym))
        if p == "/api/sentiment":
            return _r(200, a.sentiment(sym))
        if p == "/api/tiers":
            return _r(200, jobs.CACHE.get("tiers") or a.tiers())
        if p == "/api/scan/pattern" and method == "POST":
            syms = data.get("syms")
            syms = analysis.all_syms() if syms == "all" else (syms if isinstance(syms, list) and syms else None)
            return _r(200, scanner.scan_pattern(data.get("points", []), data.get("tfs") or ["15m"], int(data.get("min", 70)), syms))
        if p == "/api/suggestions":
            return _r(200, jobs.CACHE.get("suggestions") or scanner.suggestions())
        if p == "/api/suggestions/refresh" and method == "POST":
            jobs.refresh()
            return _r(200, jobs.CACHE.get("suggestions", []))
        if p == "/api/watchlist":
            if method == "POST":
                base = config.base_watchlist()
                coins = []
                for x in data.get("coins") or []:
                    x = re.sub(r"[^A-Z0-9]", "", str(x).upper().replace("USDT", ""))[:12]
                    if len(x) >= 2 and x not in base and x not in coins:
                        coins.append(x)
                if len(base) + len(coins) > config.MAX_WATCH:
                    return _r(400, {"error": f"at most {config.MAX_WATCH} coins in the watchlist"})
                store.kv_set("watchlist", coins)
                threading.Timer(2.0, lambda: os.execv(sys.executable, [sys.executable] + sys.argv)).start()  # collector reads the list at start
                return _r(200, {"ok": True, "restart": True})
            return _r(200, {"coins": config.watchlist(), "fixed": config.base_watchlist(), "max": config.MAX_WATCH})
        if p == "/api/vision":
            sym = str(qs.get("sym", ["BTCUSDT"])[0]).upper()
            sym = sym if sym.endswith("USDT") else sym + "USDT"
            return _r(200, vision.pump_study(sym, qs.get("day", [""])[0]))
        if p == "/api/backtest" and method == "POST":
            keep = ("strategy", "params", "sym", "tf", "n", "cap", "lev", "sl", "tp", "fee", "code")
            return _r(200, backtester.run(**{k: v for k, v in data.items() if k in keep}))
        if p == "/api/news":
            return _r(200, news.headlines(_ask_fn()))
        if p == "/api/calendar":
            return _r(200, news.calendar())
        if p == "/api/journal":
            if method == "POST":
                return _r(200, {"id": store.journal_add(data)})
            if method == "DELETE":
                store.journal_del(_q(qs, "id", 0, int))
                return _r(200, {"ok": True})
            return _r(200, store.journal_list())
        for name, default in (("drawings", []), ("settings", {}), ("watchlist", [])):
            if p == "/api/" + name:
                if method == "POST":
                    store.kv_set(name, data.get("value", data))
                    return _r(200, {"ok": True})
                if method == "DELETE":
                    store.kv_set(name, default)
                    return _r(200, {"ok": True})
                return _r(200, store.kv_get(name, default))
        if p == "/api/agents":
            if method == "POST":
                return _r(200, {"id": store.agent_save(data)})
            if method == "DELETE":
                store.agent_del(_q(qs, "id", 0, int))
                return _r(200, {"ok": True})
            return _r(200, store.agents_list())
        if p == "/api/agents/link" and method == "POST":
            store.link(data["a"], data["b"], data.get("on", True))
            return _r(200, {"ok": True})
        if p == "/api/ask" and method == "POST":
            return _r(200, agents.ask(data["agent"], str(data.get("text", ""))[:2000], data.get("ctx")))
        if p == "/api/health":
            return _r(200, _sys_health())
        if p == "/api/admin/password" and method == "POST":
            if not auth.check_password(str(data.get("current", ""))):
                raise ValueError("current password is wrong")
            auth.set_password(str(data.get("password", "")))
            return _r(200, {"ok": True})
        return _r(404, {"error": "not found"})
    except ValueError as e:
        return _r(400, {"error": str(e)})
    except Exception as e:  # never leak a traceback
        return _r(500, {"error": f"{type(e).__name__}: {e}"[:200]})