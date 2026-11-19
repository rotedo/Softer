"""Gemini agents with a tool loop. Tools are read-only data + backtests + drawings. NO access to settings, keys, passwords, files.

Settings that matter (all done here, in the API call - this is what the Gemini *app* does not let you control):
  * temperature 0, topP 1, one candidate        -> same question + same data = same answer, no "creativity"
  * system prompt: answer ONLY from tool results, say "data not available" otherwise
  * backup key: GEMINI_API_KEY is tried first, then GEMINI_API_KEY_2 (on 429 / 5xx / network error / blocked key)
"""
import json, os, urllib.error, urllib.request
import aggregator as a, analysis, backtester as bt, config, news, scanner, store

MODEL = lambda: config.get("GEMINI_MODEL") or "gemini-3.8-flash"
URL = "https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent"
RETRY_CODES = (403, 408, 429, 500, 502, 503, 504)  # another key may work for these; 400/404 (bad request / bad model) will not


def keys(primary=None):
    """agent's own key first, then config.py key 1, server env GEMINI_API_KEY, then key 2 (backup). Duplicates and blanks dropped."""
    out = []
    for k in (primary, config.get("GEMINI_API_KEY_1"), os.environ.get("GEMINI_API_KEY"), config.get("GEMINI_API_KEY_2")):
        if k and k.strip() and k.strip() not in out:
            out.append(k.strip())
    return out


def gemini(key, system, text, timeout=40, json_mode=False):
    """key: one key or a list. Tries each key in order; raises RuntimeError with Google's own message if all fail."""
    ks = [key] if isinstance(key, str) else list(key or [])
    ks = keys(ks[0] if ks else None) if len(ks) <= 1 else ks
    cfg = {"temperature": 0, "topP": 1, "candidateCount": 1}
    if json_mode:
        cfg["responseMimeType"] = "application/json"
    body = json.dumps({"systemInstruction": {"parts": [{"text": system}]}, "contents": [{"role": "user", "parts": [{"text": text}]}],
                       "generationConfig": cfg}).encode()
    last = "no Gemini API key set (GEMINI_API_KEY)"
    for i, k in enumerate(ks):
        req = urllib.request.Request(URL.format(m=MODEL()), body, {"Content-Type": "application/json", "x-goog-api-key": k})
        try:
            d = json.loads(urllib.request.urlopen(req, timeout=timeout).read())
            return d["candidates"][0]["content"]["parts"][0]["text"]
        except urllib.error.HTTPError as e:
            try:
                msg = json.loads(e.read()).get("error", {}).get("message", "")[:160]
            except Exception:
                msg = ""
            last = f"Gemini error {e.code} (key {i + 1}/{len(ks)}): {msg}"
            if e.code not in RETRY_CODES:
                raise RuntimeError(last)
        except (KeyError, IndexError):
            last = f"Gemini returned no text (key {i + 1}/{len(ks)}) - blocked or empty answer"
        except Exception as e:  # timeout / network
            last = f"Gemini unreachable (key {i + 1}/{len(ks)}): {type(e).__name__}"
    raise RuntimeError(last)


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
}

SYS = ("You are a trading-analysis agent inside an order-flow terminal. Role: {work}\nFree tier: keep calls few. Reply with JSON ONLY, no markdown. "
       'Either {{"tool":"name","args":{{}}}} or {{"answer":"short text","draw":[{{"type":"line|box","t1":ms,"p1":price,"t2":ms,"p2":price}}]}}.\n'
       "Tools: get_levels(sym,tf), get_bundle(sym,tf), get_liq(sym), get_gex(ccy), get_book(sym), get_derivs(sym), get_tiers(), get_news(), get_calendar(), "
       "run_backtest(strategy,sym,tf,n,lev,sl,tp,code), scan_pattern(points), suggest_drawings(draw), ask_agent(agent,text){extra}. "
       "DATA-ONLY RULES: use only numbers returned by tools; never use memory or training knowledge for prices, levels or news; if a tool has no data say 'data not available'. "
       "Liquidation zones and GEX are model ESTIMATES; say so. Never give financial advice or guarantees.")

CHAT_SYS = (
    "You are the analyst of a personal order-flow terminal. The user trades crypto futures and asks about ONE selected coin.\n"
    "STRICT DATA-ONLY RULES (no creativity, no guessing):\n"
    "0. The user may select several coins or ALL coins. For more than 2 coins call scan_coins(syms) first (syms = list of coins, or \"all\"), then get_levels only for the 1-3 most interesting ones.\n"
    "1. Every price, level, percentage or number in your answer must come from a tool result in THIS conversation. Never use memory / training knowledge for prices, news or levels.\n"
    "2. For any coin question call get_levels(sym, tf) first (add get_bundle / get_derivs / get_book / get_news only if needed). Keep calls few.\n"
    "3. If a tool returns empty, an error, or something is missing, say 'data not available' for that part. Do not fill gaps.\n"
    "4. Liquidation zones and GEX are model ESTIMATES. Use the word 'confirmed' ONLY when a zone's status is 'confirmed' (price traded through it and aggressive flow / real liquidation prints followed). A reversal zone 'score' is how many independent sources agree, not a probability.\n"
    "5. A green candle with hidden_selling_on_green = true means sellers dominated inside a rising candle (bearish warning); hidden_buying_on_red the opposite.\n"
    "6. Give conditional setups from the data: where price must react, what would confirm it, where it is wrong (invalidation). Entry / stop / target must be levels that appear in the tool data. No guarantees, not financial advice.\n"
    "7. Answer in the user's language (Hindi / Hinglish if they write that way). Short, bullet points, mention the tool name in [brackets] after the facts it supplied.\n"
    "8. If you want the chart to show something, add draw items (line or box) using prices from tool data.\n"
    'Reply with JSON ONLY: either {"tool":"name","args":{}} or {"answer":"text","draw":[{"type":"line|box","t1":ms,"p1":price,"t2":ms,"p2":price}]}.\n'
    "Use ALL data types in get_levels: GEX walls, liquidation zones, volume POC/VAH/VAL, sweeps, whales, hidden buying/selling, order-book imbalance, funding/OI, last-24h high/low/VWAP, reversal zones.\n"
    "Tools: scan_coins(syms,tf), get_levels(sym,tf), get_bundle(sym,tf), get_liq(sym), get_gex(ccy), get_book(sym), get_derivs(sym), get_tiers(), get_news(), get_calendar(), "
    "run_backtest(strategy,sym,tf,n,lev,sl,tp), scan_pattern(points).")


def _loop(system, msg, key, ag=None, depth=0):
    """The tool loop shared by agents and the chat. ag = agent dict (canvas agents) or None (chat)."""
    draws, trace = [], []
    for _ in range(6):
        raw = gemini(key, system, msg, json_mode=True).strip().strip("`").removeprefix("json").strip()
        try:
            r = json.loads(raw)
        except Exception:
            return {"answer": raw[:1500], "draw": draws, "trace": trace}
        if not isinstance(r, dict):
            return {"answer": raw[:1500], "draw": draws, "trace": trace}
        if "answer" in r:
            return {"answer": str(r["answer"])[:2500], "draw": (r.get("draw") or []) + draws, "trace": trace}
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
        return {"answer": "Gemini API key is not set: paste it at the top of config.py (GEMINI_API_KEY_1).", "draw": [], "trace": []}
    hist = "\n".join(f"{'USER' if h.get('role') == 'user' else 'ASSISTANT'}: {str(h.get('text', ''))[:600]}" for h in (history or [])[-6:] if isinstance(h, dict))
    if isinstance(sym, list):
        sym = ", ".join(_sym({"sym": x}) for x in sym[:40]) if sym else "BTCUSDT"
    msg = f"Selected coin(s): {sym}. Chart timeframe: {tf}.\n" + (f"Conversation so far:\n{hist}\n" if hist else "") + "USER QUESTION: " + str(text)[:2000]
    return _loop(CHAT_SYS, msg, ks)
