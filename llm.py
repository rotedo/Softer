"""One door for every AI provider: Gemini, Claude (Anthropic), ChatGPT (OpenAI), OpenRouter, Groq, DeepSeek...
You only paste an API key. The provider is detected from the key, the model is asked from the provider itself
(so a wrong / retired model name can never give an error). Optional: type a model name in Settings to force one.
"""
import json, threading, time, urllib.error, urllib.request

TL = threading.local()  # TL.search = True -> Gemini may use Google Search for this call

PROVIDERS = {
    "gemini":     {"label": "Gemini",     "base": "https://generativelanguage.googleapis.com/v1beta"},
    "claude":     {"label": "Claude",     "base": "https://api.anthropic.com/v1"},
    "openai":     {"label": "ChatGPT",    "base": "https://api.openai.com/v1"},
    "openrouter": {"label": "OpenRouter", "base": "https://openrouter.ai/api/v1"},
    "groq":       {"label": "Groq",       "base": "https://api.groq.com/openai/v1"},
    "deepseek":   {"label": "DeepSeek",   "base": "https://api.deepseek.com/v1"},
    "custom":     {"label": "Custom API", "base": ""},  # any OpenAI-compatible service: you give the address (base URL) in Settings
}
# best-first words used to choose among the models the provider lists
PREFER = {
    "gemini": ["flash", "pro"], "claude": ["sonnet", "haiku", "opus"], "openai": ["gpt-5", "gpt-4.1", "gpt-4o", "mini"],
    "openrouter": ["claude", "gpt", "gemini"], "groq": ["llama", "mixtral"], "deepseek": ["chat"], "custom": ["chat", "gpt", "llama", "qwen"],
}
SKIP = ("embedding", "embed", "tts", "whisper", "image", "vision-preview", "audio", "realtime", "moderation", "transcribe", "dall", "imagen", "veo", "aqa", "learnlm", "gemma", "thinking-exp")
RETRY = (401, 403, 408, 429, 500, 502, 503, 504, 529)
_MODELS = {}  # (provider, key tail) -> (time, [ids])


def detect(key):
    k = (key or "").strip()
    if k.startswith("AIza"):
        return "gemini"
    if k.startswith("sk-ant-"):
        return "claude"
    if k.startswith("sk-or-"):
        return "openrouter"
    if k.startswith("gsk_"):
        return "groq"
    if k.startswith("sk-"):
        return "openai"  # DeepSeek keys also start with sk-: pick DeepSeek in Settings if it is one
    return "openai"


def _base(provider):
    if provider == "custom":
        b = (getattr(TL, "base", "") or "").rstrip("/")
        if not b.startswith("http"):
            raise RuntimeError("Custom API: add the base URL (like https://api.example.com/v1) in Settings")
        return b
    return PROVIDERS[provider]["base"]


def _http(url, headers, body=None, timeout=40):
    req = urllib.request.Request(url, json.dumps(body).encode() if body is not None else None, headers)
    return json.loads(urllib.request.urlopen(req, timeout=timeout).read())


def _hdr(provider, key):
    if provider == "gemini":
        return {"Content-Type": "application/json", "x-goog-api-key": key}
    if provider == "claude":
        return {"Content-Type": "application/json", "x-api-key": key, "anthropic-version": "2023-06-01"}
    return {"Content-Type": "application/json", "Authorization": "Bearer " + key}


def models(provider, key):
    """ids the provider says this key can use (cached 6 h)"""
    base = _base(provider)
    ck = (provider, key[-8:], base)
    if ck in _MODELS and time.time() - _MODELS[ck][0] < 21600:
        return _MODELS[ck][1]
    ids = []
    if provider == "gemini":
        d = _http(base + "/models?pageSize=200", _hdr(provider, key), timeout=20)
        ids = [m["name"].split("/")[-1] for m in d.get("models", []) if "generateContent" in m.get("supportedGenerationMethods", [])]
    else:
        d = _http(base + "/models" + ("?limit=100" if provider == "claude" else ""), _hdr(provider, key), timeout=20)
        ids = [m["id"] for m in d.get("data", [])]
    ids = [i for i in ids if not any(s in i.lower() for s in SKIP)]
    _MODELS[ck] = (time.time(), ids)
    return ids


def pick_model(provider, key, want=""):
    ids = models(provider, key)
    if want and want in ids:
        return want
    for w in PREFER.get(provider, []):
        c = sorted([i for i in ids if w in i.lower() and "preview" not in i.lower() and "exp" not in i.lower()] or [i for i in ids if w in i.lower()], reverse=True)
        if c:
            return c[0]
    if ids:
        return sorted(ids, reverse=True)[0]
    raise RuntimeError(f"{PROVIDERS[provider]['label']}: no usable model for this key")


def _call(provider, key, model, system, text, json_mode, timeout):
    base = _base(provider)
    if provider == "gemini":
        cfg = {"temperature": 0, "topP": 1, "candidateCount": 1}
        if json_mode:
            cfg["responseMimeType"] = "application/json"
        body = {"systemInstruction": {"parts": [{"text": system}]}, "contents": [{"role": "user", "parts": [{"text": text}]}], "generationConfig": cfg}
        if getattr(TL, "search", False) and not json_mode:  # Google Search grounding (cannot be mixed with JSON mode)
            body["tools"] = [{"google_search": {}}]
        d = _http(f"{base}/models/{model}:generateContent", _hdr(provider, key), body, timeout)
        return "".join(p.get("text", "") for p in d["candidates"][0]["content"]["parts"])
    if provider == "claude":
        d = _http(base + "/messages", _hdr(provider, key), {"model": model, "max_tokens": 2000, "temperature": 0, "system": system, "messages": [{"role": "user", "content": text}]}, timeout)
        return "".join(b.get("text", "") for b in d["content"] if b.get("type") == "text")
    body = {"model": model, "temperature": 0, "messages": [{"role": "system", "content": system}, {"role": "user", "content": text}]}
    if json_mode and provider in ("openai", "groq", "deepseek"):
        body["response_format"] = {"type": "json_object"}
    try:
        d = _http(base + "/chat/completions", _hdr(provider, key), body, timeout)
    except urllib.error.HTTPError as e:
        if e.code == 400 and "temperature" in (e.read() or b"").decode("utf8", "ignore"):  # some new models accept only the default temperature
            body.pop("temperature")
            d = _http(base + "/chat/completions", _hdr(provider, key), body, timeout)
        else:
            raise
    return d["choices"][0]["message"]["content"]


def candidates(prov, key, want="", n=5):
    """models to try, best first. A model with no quota / retired / overloaded is simply skipped for the next one"""
    out = []
    if want:
        out.append(want)
    try:
        ids = models(prov, key)
        try:
            out.append(pick_model(prov, key, want))
        except RuntimeError:
            pass
        for w in PREFER.get(prov, []):
            out += sorted([m for m in ids if w in m.lower() and "preview" not in m.lower() and "exp" not in m.lower()], reverse=True)
        out += [m for m in ids if "preview" not in m.lower()]
    except Exception:
        if not out:
            raise
    seen, res = set(), []
    for m in out:
        if m and m not in seen:
            seen.add(m)
            res.append(m)
    return res[:n]


def _msg(h):
    try:
        m = json.loads(h.read().decode("utf8", "ignore")).get("error") or {}
        return (m.get("message") if isinstance(m, dict) else str(m))[:140]
    except Exception:
        return ""


def complete(entries, system, text, json_mode=False, timeout=40):
    """entries: [{'provider','key','model','base'}] tried in order. Inside one key, if a model is wrong, retired, out of quota or busy,
    the next model of that provider is tried automatically (up to 5), so any Gemini / any provider model keeps working."""
    last = "no AI key set (Settings > AI keys)"
    for i, e in enumerate(entries):
        key, prov = e["key"], e.get("provider") or detect(e["key"])
        tag = f"{PROVIDERS[prov]['label']} key {i + 1}/{len(entries)}"
        TL.base = e.get("base", "")
        try:
            tried = 0
            for model in candidates(prov, key, e.get("model", "")):
                tried += 1
                try:
                    return _call(prov, key, model, system, text, json_mode, timeout)
                except urllib.error.HTTPError as h:
                    last = f"{tag} [{model}]: error {h.code} {_msg(h)}"
                    if h.code in (401, 403):
                        break  # the key itself is refused: next key
                    if h.code not in (400, 404, 408, 429, 500, 502, 503, 504, 529):
                        raise RuntimeError(last)
                except (KeyError, IndexError):
                    last = f"{tag} [{model}]: empty answer (blocked?)"
            if not tried:
                last = f"{tag}: no usable model for this key"
        except urllib.error.HTTPError as h:
            last = f"{tag}: error {h.code} {_msg(h)}"
            if h.code not in RETRY:
                raise RuntimeError(last)
        except RuntimeError as r:
            last = f"{tag}: {r}"
        except Exception as x:
            last = f"{tag}: unreachable ({type(x).__name__})"
    raise RuntimeError(last)


def web_context(entries, question, timeout=40):
    """Google-search results as plain notes, for ANY provider: Gemini does the searching, the answer is then written by whichever AI you use"""
    gem = [e for e in entries if (e.get("provider") or detect(e["key"])) == "gemini"]
    if not gem:
        return ""
    TL.search = True
    try:
        return complete(gem, "You are a news researcher. Use Google Search. Give the latest relevant facts and news with dates in 8 short bullet lines. No opinions.", question[:500], timeout=timeout)[:2500]
    except Exception:
        return ""
    finally:
        TL.search = False


def transcribe(entries, audio_b64, mime="audio/webm", timeout=60):
    """speech -> text with Gemini (understands mixed Hindi + English, trading words stay in English letters). Same key as chat, no extra key."""
    ks = [e for e in entries if (e.get("provider") or detect(e["key"])) == "gemini"]
    if not ks:
        raise ValueError("Voice typing needs a Gemini API key (Settings > AI keys)")
    prompt = ("Transcribe this voice message exactly. The speaker mixes Hindi and English (Hinglish). Write Hindi words in Devanagari and English words "
              "in English letters. Trading words stay in English: BTC, ETH, long, short, leverage, stop loss, SL, TP, trailing, pump, spike, screener, "
              "liquidity, funding, open interest, order book, candle, 5x, USDT. Do not translate, do not add or summarise, no quotes. Output only the text.")
    body = {"contents": [{"role": "user", "parts": [{"text": prompt}, {"inline_data": {"mime_type": mime.split(";")[0], "data": audio_b64}}]}],
            "generationConfig": {"temperature": 0}}
    last = "voice failed"
    for e in ks:
        for model in candidates("gemini", e["key"], e.get("model", "")):
            try:
                d = _http(f"{PROVIDERS['gemini']['base']}/models/{model}:generateContent", _hdr("gemini", e["key"]), body, timeout)
                return "".join(p.get("text", "") for p in d["candidates"][0]["content"]["parts"]).strip()
            except urllib.error.HTTPError as h:
                last = f"error {h.code} {_msg(h)}"
                if h.code in (401, 403):
                    break
            except (KeyError, IndexError):
                last = "empty answer"
    raise RuntimeError("Voice: " + last)
          
