"""The sensors of the turbine. Every sensor is ONE function that gets the candles up to NOW only (the last candle is the one being judged;
it never sees a later candle) and returns (True/False, short note). Numbers come from pump_config.STRATEGY_CONFIG, so you tune them in the /pump page.
Candle = dict {t,o,h,l,c,v,q,tb,oi,fr}: q = quote volume, tb = taker-buy volume or None, oi = open interest or None, fr = funding rate or None.
To add a sensor: write one function with @strategy("name") here and add "name": {"enabled": True, ...} to STRATEGY_CONFIG in pump_config.py."""
import pump_config as cfg

REG = {}


def strategy(name):
    def deco(fn):
        REG[name] = fn
        return fn
    return deco


def run_all(candles, only=None):
    """-> {name: (ok, note)} for every enabled sensor (or only those named in `only`)"""
    out = {}
    for name, fn in REG.items():
        conf = cfg.STRATEGY_CONFIG.get(name)
        if not conf or not conf.get("enabled") or (only and name not in only):
            continue
        try:
            out[name] = fn(candles, conf)
        except Exception as e:  # one broken sensor must not stop the others
            out[name] = (False, f"error: {e}")
    return out


@strategy("volume_spike")
def volume_spike(c, conf):
    n = int(conf["base_candles"])
    if len(c) < n + 1:
        return False, "not enough candles"
    avg = sum(x["q"] for x in c[-n - 1:-1]) / n
    cur = c[-1]
    if avg <= 0:
        return False, "no volume"
    mult = cur["q"] / avg
    ok = mult >= conf["volume_multiplier"] and cur["c"] > cur["o"]
    if ok and conf["min_buy_ratio"] > 0 and cur.get("tb") is not None and cur["v"] > 0:
        ok = cur["tb"] / cur["v"] >= conf["min_buy_ratio"]
    return ok, f"volume {mult:.1f}x average"


@strategy("price_momentum")
def price_momentum(c, conf):
    b, bo = int(conf["bars"]), int(conf["breakout_candles"])
    if len(c) < max(b, bo) + 2:
        return False, "not enough candles"
    ret = (c[-1]["c"] / c[-1 - b]["c"] - 1) * 100
    last = c[-b - 1:]
    rising = all(last[i]["h"] >= last[i - 1]["h"] and last[i]["l"] >= last[i - 1]["l"] for i in range(1, len(last)))
    breakout = c[-1]["c"] > max(x["h"] for x in c[-1 - bo:-1])
    return ret >= conf["min_return_pct"] and rising and breakout, f"{ret:+.1f}% in {b} candles, breakout={breakout}"


@strategy("open_interest")
def open_interest(c, conf):
    if len(c) < 14 or c[-1].get("oi") is None or c[-13].get("oi") is None or c[-13]["oi"] <= 0:
        return False, "no open-interest data"
    ch = (c[-1]["oi"] / c[-13]["oi"] - 1) * 100
    px = (c[-1]["c"] / c[-13]["c"] - 1) * 100
    return ch >= conf["oi_change_percent"] and px > conf["min_price_pct"], f"open interest {ch:+.1f}% in 1h, price {px:+.1f}%"


@strategy("funding_rate")
def funding_rate(c, conf):
    fr = c[-1].get("fr")
    if fr is None:
        return False, "no funding data"
    return fr <= conf["negative_below"] or fr >= conf["positive_above"], f"funding {fr * 100:+.3f}%"


@strategy("oi_build")
def oi_build(c, conf):
    k = int(conf["candles"])
    if len(c) < k + 1 or c[-1].get("oi") is None or c[-1 - k].get("oi") is None or c[-1 - k]["oi"] <= 0:
        return False, "no open-interest data"
    ch = (c[-1]["oi"] / c[-1 - k]["oi"] - 1) * 100
    px = (c[-1]["c"] / c[-1 - k]["c"] - 1) * 100
    return ch >= conf["oi_change_percent"] and px <= conf["max_price_pct"], f"open interest {ch:+.1f}% while price {px:+.1f}% over {k} candles"


@strategy("trades_spike")
def trades_spike(c, conf):
    n = int(conf["base_candles"])
    if len(c) < n + 1 or c[-1].get("n") is None:
        return False, "no trade-count data"
    avg = sum(x["n"] for x in c[-n - 1:-1]) / n
    m = c[-1]["n"] / avg if avg > 0 else 0
    return m >= conf["multiplier"] and c[-1]["c"] > c[-1]["o"], f"trades {m:.1f}x average"


@strategy("range_expansion")
def range_expansion(c, conf):
    n = int(conf["base_candles"])
    if len(c) < n + 1:
        return False, "not enough candles"
    rg = lambda x: (x["h"] - x["l"]) / x["o"] if x["o"] > 0 else 0
    avg = sum(rg(x) for x in c[-n - 1:-1]) / n
    m = rg(c[-1]) / avg if avg > 0 else 0
    return m >= conf["multiplier"] and c[-1]["c"] > c[-1]["o"], f"candle range {m:.1f}x average"


# ---------------- YOUR OWN SETUPS (written in pump_custom.py) ----------------
CUSTOM, CUSTOM_ERROR = {}, ""


def custom(name):
    """decorator for your own setups in pump_custom.py: function(candles) -> (True/False, note). Backtested as view 'my_<name>', alerted live on Telegram."""
    def deco(fn):
        CUSTOM[name] = fn
        return fn
    return deco


def run_custom(candles):
    out = {}
    for name, fn in CUSTOM.items():
        try:
            r = fn(candles)
            out[name] = (bool(r[0]), str(r[1])) if isinstance(r, tuple) else (bool(r), "")
        except Exception as e:
            out[name] = (False, f"error: {e}")
    return out


try:  # a mistake in your own file must never break the rest
    import pump_custom  # noqa: F401
except ImportError:
    pass
except Exception as _e:
    CUSTOM_ERROR = f"pump_custom.py: {type(_e).__name__}: {_e}"
