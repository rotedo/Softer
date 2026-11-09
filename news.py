"""Economic calendar + crypto headlines (titles and links only; ranking by keywords or Gemini)."""
import json, os, time, urllib.request, xml.etree.ElementTree as ET
from datetime import datetime

CAL_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
FEEDS = {"CoinDesk": "https://www.coindesk.com/arc/outboundfeeds/rss/", "Cointelegraph": "https://cointelegraph.com/rss"}
KEYS = ("fed", "cpi", "nfp", "etf", "hack", "sec ", "binance", "rate", "liquidat", "fomc", "inflation", "ban", "lawsuit", "exploit")
_CACHE = {}


def _get(url, timeout=8):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 orderflow-terminal"})
    return urllib.request.urlopen(req, timeout=timeout).read()


def _cached(k, ttl, fn):
    t = time.time()
    if k in _CACHE and t - _CACHE[k][0] < ttl:
        return _CACHE[k][1]
    try:
        v = fn()
        _CACHE[k] = (t, v)
        return v
    except Exception as e:
        if k in _CACHE:
            return _CACHE[k][1]
        return {"error": f"{type(e).__name__}: {e}"[:120]}


def calendar():
    def f():
        out = []
        for e in json.loads(_get(CAL_URL)):
            if e.get("country") != "USD" or e.get("impact") not in ("High", "Medium"):
                continue
            try:
                ts = int(datetime.fromisoformat(e["date"]).timestamp() * 1000)
            except Exception:
                continue
            out.append({"title": e.get("title"), "country": "USD", "ts": ts, "impact": e["impact"], "forecast": e.get("forecast"), "previous": e.get("previous")})
        return sorted(out, key=lambda x: x["ts"])
    return _cached("cal", 1800, f)


def _rss(name, url):
    root = ET.fromstring(_get(url))
    return [{"title": (i.findtext("title") or "").strip(), "link": (i.findtext("link") or "").strip(), "source": name} for i in root.iter("item")][:20]


def headlines(ask=None):
    """ask: optional callable(prompt)->text (Gemini). Without it, keyword ranking."""
    def f():
        items = []
        for n, u in FEEDS.items():
            try:
                items += _rss(n, u)
            except Exception:
                pass
        return items
    items = _cached("rss", 900, f)
    if isinstance(items, dict):
        return items
    for it in items:
        s = sum(k in it["title"].lower() for k in KEYS)
        it["impact"] = "High" if s >= 2 else "Medium" if s == 1 else "Low"
        it["summary"] = ""
    items.sort(key=lambda x: {"High": 0, "Medium": 1, "Low": 2}[x["impact"]])
    items = items[:15]
    if ask and items:
        try:
            r = ask("Rank these crypto headlines by likely market impact and write a one-line (max 15 words) summary in your own words for each. "
                    'Reply JSON only: [{"i":index,"impact":"High|Medium|Low","summary":"..."}]\n' + "\n".join(f"{i}. {x['title']}" for i, x in enumerate(items)))
            for r_ in json.loads(r.strip().strip("`").removeprefix("json").strip()):
                it = items[int(r_["i"])]
                it["impact"], it["summary"] = r_.get("impact", it["impact"]), r_.get("summary", "")[:160]
        except Exception:
            pass
    return items
