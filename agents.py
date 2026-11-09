"""Gemini agents with a tool loop. Tools are read-only data + backtests + drawings. NO access to settings, keys, passwords, files."""
import json, os, urllib.error, urllib.request
import aggregator as a, backtester as bt, news, scanner, store

MODEL = lambda: os.environ.get("GEMINI_MODEL", "gemini-3.8-flash")
URL = "https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent"


def gemini(key, system, text, timeout=40):
    body = json.dumps({"systemInstruction": {"parts": [{"text": system}]}, "contents": [{"role": "user", "parts": [{"text": text}]}],
                       "generationConfig": {"temperature": 0.3}}).encode()
    req = urllib.request.Request(URL.format(m=MODEL()), body, {"Content-Type": "application/json", "x-goog-api-key": key})
    try:
        d = json.loads(urllib.request.urlopen(req, timeout=timeout).read())
        return d["candidates"][0]["content"]["parts"][0]["text"]
    except urllib.error.HTTPError as e:
        if e.code == 429:
            raise RuntimeError("Gemini free limit reached - try again in a minute.")
        raise RuntimeError(f"Gemini error {e.code}")


def _slim(cs):  # keep prompts small
    return [{k: c[k] for k in ("t", "o", "h", "l", "c", "delta", "bp", "im", "sw", "mn") if k in c} for c in cs[-40:]]


TOOLS = {
    "get_bundle": lambda g, **k: _slim(a.bundle(k.get("sym", "BTCUSDT"), k.get("tf", "15m"), 60)["candles"]),
    "get_liq": lambda g, **k: a.liq_zones(k.get("sym", "BTCUSDT"))[:15],
    "get_gex": lambda g, **k: a.gex(k.get("ccy", "BTC")),
    "get_book": lambda g, **k: a.book(k.get("sym", "BTCUSDT")),
    "get_tiers": lambda g, **k: a.tiers(),
    "get_news": lambda g, **k: news.headlines()[:8],
    "get_calendar": lambda g, **k: (news.calendar() or [])[:10],
    "run_backtest": lambda g, **k: {x: v for x, v in bt.run(**{q: k[q] for q in ("strategy", "sym", "tf", "n", "lev", "sl", "tp", "code") if q in k}).items() if x in ("stats", "explain")},
    "scan_pattern": lambda g, **k: scanner.scan_pattern(k["points"], k.get("tfs", ["15m"]), k.get("min", 70))[:5],
    "suggest_drawings": lambda g, **k: {"_draw": k.get("draw", [])},
}

SYS = ("You are a trading-analysis agent inside an order-flow terminal. Role: {work}\nFree tier: keep calls few. Reply with JSON ONLY, no markdown. "
       'Either {{"tool":"name","args":{{}}}} or {{"answer":"short text","draw":[{{"type":"line|box","t1":ms,"p1":price,"t2":ms,"p2":price}}]}}.\n'
       "Tools: get_bundle(sym,tf), get_liq(sym), get_gex(ccy), get_book(sym), get_tiers(), get_news(), get_calendar(), run_backtest(strategy,sym,tf,n,lev,sl,tp,code), "
       "scan_pattern(points), suggest_drawings(draw), ask_agent(agent,text){extra}. Liquidation zones and GEX are model ESTIMATES; say so. Never give financial advice or guarantees.")


def ask(agent_id, text, ctx=None, depth=0):
    ag = next((x for x in store.agents_list(True)["agents"] if x["id"] == int(agent_id)), None)
    if not ag:
        raise ValueError("agent not found")
    key = ag["key"] or os.environ.get("GEMINI_API_KEY", "")
    if not key:
        return {"answer": "No API key set for this agent.", "draw": []}
    extra = ", link_agents(a,b,on) [main agent only]" if ag["main"] else ""
    system = SYS.format(work=ag["work"] or "general analyst", extra=extra)
    msg, draws = (text + ("\nContext: " + json.dumps(ctx)[:1500] if ctx else "")), []
    for _ in range(6):
        raw = gemini(key, system, msg).strip().strip("`").removeprefix("json").strip()
        try:
            r = json.loads(raw)
        except Exception:
            return {"answer": raw[:1500], "draw": draws}
        if "answer" in r:
            return {"answer": str(r["answer"])[:2000], "draw": (r.get("draw") or []) + draws}
        name, args = r.get("tool"), r.get("args") or {}
        try:
            if name == "ask_agent":
                if depth >= 2 or not store.linked(ag["id"], int(args.get("agent", 0))):
                    res = "not linked on the canvas"
                else:
                    res = ask(args["agent"], args.get("text", ""), None, depth + 1)["answer"]
            elif name == "link_agents" and ag["main"]:
                store.link(args["a"], args["b"], bool(args.get("on", True)))
                res = "ok"
            elif name in TOOLS:
                res = TOOLS[name](ag, **args)
                if isinstance(res, dict) and "_draw" in res:
                    draws += res["_draw"]
                    res = "drawings queued"
            else:
                res = "unknown tool"
        except Exception as e:
            res = f"tool error: {e}"[:200]
        msg += f"\nTOOL {name} RESULT: " + json.dumps(res, default=str)[:3500]
    return {"answer": "Agent took too many steps; ask a narrower question.", "draw": draws}
