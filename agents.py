"""AI agents (any provider: Gemini / Claude / ChatGPT / ...) with a tool loop. Tools are read-only data + backtests + drawings. NO access to settings, keys, passwords, files.

Settings that matter (all done here, in the API call - this is what the Gemini *app* does not let you control):
  * temperature 0, topP 1, one candidate        -> same question + same data = same answer, no "creativity"
  * system prompt: answer ONLY from tool results, say "data not available" otherwise
  * several keys: keys added in the app\u0027s Settings screen first (chat, then backup), then config.py / env keys (on 429 / 5xx / network error / blocked key)
"""
import vision, json, os
import aggregator as a, analysis, backtester as bt, config, news, scanner, store

import llm

MODEL = lambda: config.get("AI_MODEL") or config.get("GEMINI_MODEL") or "auto"  # "auto" = asked from the provider itself


def _entry(k, model=""):
    k = str(k).strip()
    return {"provider": llm.detect(k), "key": k, "model": model, "base": ""}


def _stored():
    """keys saved in the Settings screen: role 'chat' first, then 'backup'. Never raises."""
    try:
        ks = [k for k in store.gemini_keys(True) if k["key"] and k["role"] != "off"]
    except Exception:
        return []
    return [{"provider": k.get("provider") or llm.detect(k["key"]), "key": k["key"], "model": k.get("model", ""), "base": k.get("base", "")} for k in sorted(ks, key=lambda k: k["role"] != "chat")]


def keys(primary=None):
    """AI entries in order: agent's own key, Settings-screen keys (chat, then backup), config.py / env keys. Duplicates dropped."""
    out, seen = [], set()
    pre = [_entry(primary)] if primary and str(primary).strip() else []
    env = [_entry(k) for k in (config.get("GEMINI_API_KEY_1"), os.environ.get("GEMINI_API_KEY"), config.get("GEMINI_API_KEY_2"), config.get("AI_API_KEY")) if k and k.strip()]
    for e in pre + _stored() + env:
        if e["key"] not in seen:
            seen.add(e["key"])
            out.append(e)
    return out


def test_key(entry):
    """one tiny question with exactly this key (no failover). entry = key string or entry dict"""
    e = entry if isinstance(entry, dict) else _entry(entry)
    try:
        r = llm.complete([e], "Reply with the single word OK.", "ping", timeout=25)
        return {"ok": True, "detail": llm.PROVIDERS[e["provider"]]["label"] + " (" + (e.get("model") or llm.pick_model(e["provider"], e["key"])) + ") answered: " + r.strip()[:30]}
    except RuntimeError as x:
        return {"ok": False, "detail": str(x)}


def gemini(key, system, text, timeout=40, json_mode=False, exact=False):
    """name kept for old callers - works with ANY provider. key: entry list, entry, key string or None (= all saved keys)."""
    if isinstance(key, dict):
        ks = [key]
    elif isinstance(key, str):
        ks = keys(key) if not exact else [_entry(key)]
    else:
        ks = [e if isinstance(e, dict) else _entry(e) for e in (key or [])] or keys()
    return llm.complete(ks, system, text, json_mode, timeout)


def _slim(cs):  # keep prompts small
    return [{k: c[k] for k in ("t", "o", "h", "l", "c", "delta", "bp", "im", "sw", "mn", "dv") if k in c} for c in cs[-40:]]


def _sym(k):
    s = str(k.get("sym", "BTCUSDT")).upper().replace("/", "").replace("-", "")
    return s if s.endswith("USDT") else s + "USDT"


def _backtest(k):
    r = bt.run(**{q: k[q] for q in ("strategy", "sym", "tf", "n", "lev", "sl", "tp", "code") if q in k})
    return {x: v for x, v in r.items() if x in ("stats", "explain")}


TOOLS = {
    "scan_coins": lambda g, **k: analysis.scan([_sym({"sym": x}) for x in k["syms"]] if isinstance(k.get("syms"), list) else "all", k.get("tf", "15m")),
    "get_levels": lambda g, **k: analysis.summary(_sym(k), k.get("tf", "15m")),
    "get_bundle": lambda g, **k: _slim(a.bundle(_sym(k), k.get("tf", "15m"), 60)["candles"]),
    "get_liq": lambda g, **k: [{x: z[x] for x in ("side", "p", "u", "status", "ev")} for z in analysis.chart(_sym(k), "15m", 100)["levels"]["liq"][:15]],
    "get_gex": lambda g, **k: a.gex(k.get("ccy", "BTC")),
    "get_book": lambda g, **k: a.book(_sym(k)),
    "get_derivs": lambda g, **k: analysis.derivs(_sym(k)),
    "get_tiers": lambda g, **k: a.tiers(),
    "get_news": lambda g, **k: news.headlines()[:8],
    "get_calendar": lambda g, **k: (news.calendar() or [])[:10],
    "run_backtest": lambda g, **k: _backtest(k),
    "scan_pattern": lambda g, **k: scanner.scan_pattern(k["points"], k.get("tfs", ["15m"]), k.get("min", 70))[:5],
    "suggest_drawings": lambda g, **k: {"_draw": k.get("draw", [])},
    "vision_study": lambda g, **k: vision.pump_study(_sym(k), str(k.get("day", ""))),
    "save_script": lambda g, **k: {"saved_id": __import__("screener").save_script({"name": k.get("name"), "code": k.get("code"), "tf": k.get("tf", "15m"), "on": False}), "note": "saved OFF; the user turns it ON in the Scripts tab"},
}

SYS = ("You are a trading-analysis agent inside an order-flow terminal. Role: {work}\nFree tier: keep calls few. Reply with JSON ONLY, no markdown. "
       'Either {{"tool":"name","args":{{}}}} or {{"answer":"short text","draw":[{{"type":"line|box","t1":ms,"p1":price,"t2":ms,"p2":price}}]}}.\n'
       "Tools: get_levels(sym,tf), get_bundle(sym,tf), get_liq(sym), get_gex(ccy), get_book(sym), get_derivs(sym), get_tiers(), get_news(), get_calendar(), "
       "run_backtest(strategy,sym,tf,n,lev,sl,tp,code), scan_pattern(points), suggest_drawings(draw), save_script(name,code,tf), ask_agent(agent,text){extra}. "
       "DATA-ONLY RULES: use only numbers returned by tools; never use memory or training knowledge for prices, levels or news; if a tool has no data say 'data not available'. "
       "Liquidation zones and GEX are model ESTIMATES; say so. Never give financial advice or guarantees.")

CHAT_SYS = (
    "You are the analyst of a personal order-flow terminal. The user trades crypto futures and asks about ONE selected coin.\n"
    "STRICT DATA-ONLY RULES (no creativity, no guessing):\n"
    "0. The user may select several coins or ALL coins. For more than 2 coins call scan_coins(syms) first (syms = list of coins, or \"all\"), then get_levels only for the 1-3 most interesting ones.\n"
    "1. Every price, level, percentage or number in your answer must come from a tool result in THIS conversation. Never use memory / training knowledge for prices, news or levels.\n"
    "2. For any coin question call get_levels(sym, tf) first (add get_bundle / get_derivs / get_book / get_news only if needed). Keep calls few.\n"
    "3. If a tool returns empty, an error, or something is missing, say 'data not available' for that part. Do not fill gaps.\n"
    "3b. EXCEPTION for coins outside the watchlist: order-flow parts (delta, liquidation zones, GEX, order book) may be missing, but candles exist. Then call get_bundle(sym,tf) and derive levels from the candles yourself (recent swing highs and lows, round numbers, high-volume candles, simple trend) and label them 'candle-based'. Never refuse the whole question because order-flow is missing. For 'pick the best N coins' questions: scan_coins first, then get_bundle on the top few, rank by volume spike, range and trend, and say why.\n"
    "3c. For 'what happened before this pump' questions call vision_study(sym, day) (day = YYYY-MM-DD, a past UTC day) and explain only what it returns.\n"
    "4. Liquidation zones and GEX are model ESTIMATES. Use the word 'confirmed' ONLY when a zone's status is 'confirmed' (price traded through it and aggressive flow / real liquidation prints followed). A reversal zone 'score' is how many independent sources agree, not a probability.\n"
    "5. A green candle with hidden_selling_on_green = true means sellers dominated inside a rising candle (bearish warning); hidden_buying_on_red the opposite.\n"
    "6. Give conditional setups from the data: where price must react, what would confirm it, where it is wrong (invalidation). Entry / stop / target must be levels that appear in the tool data. No guarantees, not financial advice.\n"
    "7. Answer in the user's language (Hindi / Hinglish if they write that way). Short, bullet points, mention the tool name in [brackets] after the facts it supplied.\n"
    "8. If you want the chart to show something, add draw items (line or box) using prices from tool data.\n"
    'Reply with JSON ONLY: either {"tool":"name","args":{}} or {"answer":"text","draw":[{"type":"line|box","t1":ms,"p1":price,"t2":ms,"p2":price}]}.\n'
    "Use ALL data types in get_levels: GEX walls, liquidation zones, volume POC/VAH/VAL, sweeps, whales, hidden buying/selling, order-book imbalance, funding/OI, last-24h high/low/VWAP, reversal zones.\n"
    "Tools: scan_coins(syms,tf), get_levels(sym,tf), get_bundle(sym,tf), get_liq(sym), get_gex(ccy), get_book(sym), get_derivs(sym), get_tiers(), get_news(), get_calendar(), "
    "run_backtest(strategy,sym,tf,n,lev,sl,tp), scan_pattern(points), vision_study(sym,day), save_script(name,code,tf).\n"
    "9. save_script: when the user asks for an alert/screener rule, write Python defining signals(c, f) (returns a list: 1 long, -1 short, 0 none, one per candle; c[i] has t,o,h,l,c,v,delta,bp,cvd; f has delta,bp,cvd,body,upper,lower; helpers sma ema highest lowest atr math; no imports) and save it. It is saved OFF and fires Telegram alerts on Tier 1/2 coins once the user turns it ON.")


def _loop(system, msg, key, ag=None, depth=0):
    """The tool loop shared by agents and the chat. ag = agent dict (canvas agents) or None (chat)."""
    draws, trace = [], []
    for _ in range(5):
        raw = gemini(key, system, msg, json_mode=True).strip().strip("`").removeprefix("json").strip()
        try:
            r = json.loads(raw)
        except Exception:
            return {"answer": raw[:1500], "draw": draws, "trace": trace}
        if not isinstance(r, dict):
            return {"answer": raw[:1500], "draw": draws, "trace": trace}
        if "answer" in r:
            return {"answer": str(r["answer"])[ :2500], "draw": (r.get("draw") or []) + draws, "trace": trace}
        name, args = r.get("tool"), r.get("args") or {}
        try:
            if ag and name == "ask_agent":
                if depth >= 2 or not store.linked(ag["id"], int(args.get("agent", 0))):
                    res = "not linked on the canvas"
                else:
                    res = ask(args["agent"], args.get("text", ""), None, depth + 1)["answer"]
            elif ag and name == "link_agents" and ag["main"]:
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
        out = json.dumps(res, default=str)
        trace.append({"tool": name, "args": args, "result": out[:600]})
        msg += f"\nTOOL {name} RESULT: " + out[:6000]
    return {"answer": "Took too many steps; ask a narrower question.", "draw": draws, "trace": trace}


def ask(agent_id, text, ctx=None, depth=0):
    ag = next((x for x in store.agents_list(True)["agents"] if x["id"] == int(agent_id)), None)
    if not ag:
        raise ValueError("agent not found")
    ks = keys(ag["key"])
    if not ks:
        return {"answer": "No API key set for this agent.", "draw": []}
    extra = ", link_agents(a,b,on) [main agent only]" if ag["main"] else ""
    system = SYS.format(work=ag["work"] or "general analyst", extra=extra)
    msg = text + ("\nContext: " + json.dumps(ctx)[:1500] if ctx else "")
    return _loop(system, msg, ks, ag, depth)


def chat(sym, text, history=None, tf="15m"):
    """Terminal chat: temperature 0, data-only, backup key. Returns {answer, draw, trace} (trace = which tools ran and what they returned)."""
    ks = keys()
    if not ks:
        return {"answer": "No AI key yet: open Settings and paste any key (Gemini, Claude, ChatGPT...).", "draw": [], "trace": []}
    hist = "\n".join(f"{'USER' if h.get('role') == 'user' else 'ASSISTANT'}: {str(h.get('text', ''))[:600]}" for h in (history or [])[-6:] if isinstance(h, dict))
    if isinstance(sym, list):
        sym = ", ".join(_sym({"sym": x}) for x in sym[:40]) if sym else "BTCUSDT"
    msg = f"Selected coin(s): {sym}. Chart timeframe: {tf}.\n" + (f"Conversation so far:\n{hist}\n" if hist else "") + "USER QUESTION: " + str(text)[:2000]
    return _loop(CHAT_SYS, msg, ks)