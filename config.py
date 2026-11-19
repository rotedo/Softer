"""=====================  EDIT ONLY THIS FILE FOR KEYS AND COINS  =====================

1) Paste your two Gemini API keys between the quotes below (main + backup).
   If the main key hits its limit or fails, the backup key is used automatically.
   !! Keep your GitHub repository PRIVATE. A key committed to a public repo gets stolen within minutes.
   (Prefer not to put keys in code? Leave them empty and set the env vars GEMINI_API_KEY / GEMINI_API_KEY_2 instead.)

2) WATCHLIST = coins you always want: they show in the app's Watchlist AND the collector records their full
   order-flow data (tick trades, footprint, book...) from all venues. Add coins like "SOL", "DOGE".
   Start with a few: every coin adds websocket subscriptions on 7 exchanges and database size.
"""
GEMINI_API_KEY_1 = ""      # <- main Gemini key
GEMINI_API_KEY_2 = ""      # <- backup Gemini key
GEMINI_MODEL = ""          # optional: model id, e.g. "gemini-2.5-flash". Empty = env GEMINI_MODEL or the built-in default

WATCHLIST = ["BTC", "ETH"]  # <- add your coins here, e.g. ["BTC", "ETH", "SOL", "DOGE"]

TELEGRAM_BOT_TOKEN = ""    # optional: weekly archive is sent to your Telegram chat
TELEGRAM_CHAT_ID = ""
# ====================================================================================

import os


def get(name, default=""):
    """value from this file if filled in, else the environment variable of the same name, else default"""
    v = globals().get(name)
    if isinstance(v, str) and v.strip():
        return v.strip()
    return os.environ.get(name, default)


def watchlist():
    """WATCHLIST from this file plus env WISHLIST (comma separated), upper-case, no duplicates, order kept"""
    out = []
    for b in list(WATCHLIST) + [x for x in os.environ.get("WISHLIST", "").split(",")]:
        b = str(b).strip().upper().replace("USDT", "")
        if b and b not in out:
            out.append(b)
    return out or ["BTC", "ETH"]
