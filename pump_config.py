"""All pump-system numbers live here as DEFAULTS. You change them in the /pump page (Settings), never in this file:
the page validates them, applies them in place and saves them in the app database (store.kv key 'pump_cfg').
A bad value changes nothing. 'Default पर लौटाओ' brings these numbers back."""
import copy, math, os

DATA_DIR = os.environ.get("PUMP_DATA_DIR") or os.path.join(os.path.dirname(os.path.abspath(os.environ.get("DB_PATH", "orderflow.db"))), "pump_data")

# what counts as a pump (used to LABEL pumps in old data): price rises `pct` % within `window` candles (5m candles)
# merge_candles: after one pump, the same coin cannot start another labelled pump for this many candles (288 = at most ONE pump per coin-day)
PUMP = {"pct": 30.0, "window": 288, "merge_candles": 288}
# "find pumped coins" (Binance daily candles): coins whose best day in the last `days` days gained at least min_day_gain %
FIND = {"days": 25, "min_day_gain": 30.0, "group_a": 25, "group_b": 60}
# data downloaded around each pump day (open interest history exists only for the last 30 days on Binance)
WINDOW = {"before_days": 5, "after_days": 2}
# how an alert is judged: hit = price goes up hit_pct % within horizon candles; cooldown = candles of silence after an alert;
# lookback = how many past candles a strategy may see (never future ones)
EVAL = {"hit_pct": 10.0, "horizon": 72, "cooldown": 288, "lookback": 300}
# the sensors of the turbine. Add one = one function in pump_strategies.py + one entry here.
# funding numbers are fractions (-0.0002 = -0.02%). min_buy_ratio 0 = ignore buyer share (CoinDCX candles do not carry it)
STRATEGY_CONFIG = {
    "volume_spike": {"enabled": True, "volume_multiplier": 3.0, "base_candles": 48, "min_buy_ratio": 0.0},
    "price_momentum": {"enabled": True, "min_return_pct": 2.0, "bars": 3, "breakout_candles": 24},
    "open_interest": {"enabled": True, "oi_change_percent": 5.0, "min_price_pct": 0.0},
    "funding_rate": {"enabled": True, "negative_below": -0.0002, "positive_above": 0.0008},
    # extra sensors, OFF until the lab shows they help
    "oi_build": {"enabled": False, "candles": 48, "oi_change_percent": 3.0, "max_price_pct": 5.0},
    "trades_spike": {"enabled": False, "multiplier": 3.0, "base_candles": 48},
    "range_expansion": {"enabled": False, "multiplier": 4.0, "base_candles": 48},
}
# garbage filters, applied to EVERY alert (backtest and live the same way). 0 / large value = switch that filter off
#  max_run_pct: skip if price already rose more than this % from the lowest low of the last run_candles candles (= we are late, not at the start)
#  min_candle_usd: skip thin coins: average USDT traded per 5m candle over the last 3 candles must be at least this
#  confirm_candles: sensors must agree on this many candles in a row (1 = off; 2 removes one-candle spikes)
#  max_wick_ratio: skip if the last candle closed far below its high (share of the candle range given back; 1 = off)
FILTER = {"max_run_pct": 15.0, "run_candles": 36, "min_candle_usd": 3000.0, "confirm_candles": 1, "max_wick_ratio": 0.6}
MIN_STRATEGIES = 3  # alert only when at least this many sensors agree at the same time
# live scanner (CoinDCX 5m candles for every coin, other exchanges only for data)
LIVE = {"min_quote_vol_24h": 2000000, "workers": 8, "cooldown_min": 1440, "klines": 60, "delay_s": 8}

_SECTIONS = ("PUMP", "FIND", "WINDOW", "EVAL", "STRATEGY_CONFIG", "LIVE", "FILTER")
_DEFAULT = copy.deepcopy({k: globals()[k] for k in _SECTIONS})
_DEFAULT["MIN_STRATEGIES"] = MIN_STRATEGIES
_INT = {"window", "horizon", "cooldown", "lookback", "base_candles", "bars", "breakout_candles", "group_a", "group_b", "days", "before_days",
        "after_days", "merge_candles", "workers", "klines", "cooldown_min", "MIN_STRATEGIES", "delay_s", "min_quote_vol_24h", "candles", "run_candles", "confirm_candles"}
_RANGE = {"pct": (0.1, 10000), "window": (1, 288), "merge_candles": (0, 2000), "days": (1, 30), "min_day_gain": (1, 10000), "group_a": (0, 200), "group_b": (0, 400),
          "before_days": (0, 30), "after_days": (0, 30), "hit_pct": (0.1, 10000), "horizon": (1, 2000), "cooldown": (0, 2000), "lookback": (60, 1000),
          "volume_multiplier": (1, 1000), "base_candles": (5, 288), "min_buy_ratio": (0, 1), "min_return_pct": (0, 1000), "bars": (1, 50),
          "breakout_candles": (1, 288), "oi_change_percent": (0, 1000), "min_price_pct": (-100, 1000), "candles": (3, 576), "max_run_pct": (0, 100000), "run_candles": (3, 576), "min_candle_usd": (0, 1e9), "confirm_candles": (1, 6), "max_wick_ratio": (0, 1), "max_price_pct": (0, 1000), "multiplier": (1, 1000), "negative_below": (-1, 0), "positive_above": (0, 1),
          "MIN_STRATEGIES": (1, 10), "min_quote_vol_24h": (0, 1e12), "workers": (1, 16), "cooldown_min": (0, 1440), "klines": (60, 500), "delay_s": (0, 120)}


def snapshot():
    """current numbers as a nested dict (what the Settings page shows)"""
    d = {k: copy.deepcopy(globals()[k]) for k in _SECTIONS}
    d["MIN_STRATEGIES"] = MIN_STRATEGIES
    return d


def _flat(d, p=()):
    for k, v in d.items():
        if isinstance(v, dict):
            yield from _flat(v, p + (k,))
        else:
            yield p + (k,), v


def _check(new):
    """-> (clean nested changes, errors). Nothing is applied here."""
    errors, clean = [], {}
    if not isinstance(new, dict):
        return {}, ["settings must be a dict"]
    for path, v in _flat(new):
        ref = _DEFAULT
        for k in path:
            ref = ref.get(k) if isinstance(ref, dict) else None
            if ref is None:
                break
        name = ".".join(path)
        if ref is None or isinstance(ref, dict):
            errors.append(f"unknown setting: {name}")
            continue
        key = path[-1]
        if isinstance(ref, bool):
            if isinstance(v, str):
                v = v.strip().lower() in ("1", "true", "on", "yes")
            val = bool(v)
        else:
            try:
                val = float(v)
                if not math.isfinite(val):
                    raise ValueError
            except (TypeError, ValueError):
                errors.append(f"{name}: number needed")
                continue
            lo, hi = _RANGE.get(key, (None, None))
            if lo is not None and not lo <= val <= hi:
                errors.append(f"{name}: must be between {lo:g} and {hi:g}")
                continue
            val = int(round(val)) if key in _INT else val
        t = clean
        for k in path[:-1]:
            t = t.setdefault(k, {})
        t[key] = val
    return clean, errors


def apply(new):
    """validate, then apply IN PLACE (other modules keep their references). -> list of errors; if any, nothing changed"""
    global MIN_STRATEGIES
    clean, errors = _check(new)
    if errors:
        return errors
    for sec, vals in clean.items():
        if sec == "MIN_STRATEGIES":
            MIN_STRATEGIES = vals
        elif sec == "STRATEGY_CONFIG":
            for name, kv in vals.items():
                STRATEGY_CONFIG[name].update(kv)
        else:
            globals()[sec].update(vals)
    return []


def save(new):
    """apply + remember in the app database. -> list of errors (empty = saved)"""
    errors = apply(new)
    if not errors:
        try:
            import store
            store.kv_set("pump_cfg", snapshot())
        except Exception as e:  # works for this run even if the database is not reachable
            errors = [f"applied, but could not be saved: {e}"]
    return errors


def reset():
    apply(_DEFAULT)
    try:
        import store
        store.kv_set("pump_cfg", snapshot())
    except Exception:
        pass


def load_saved():
    """re-apply what the user saved (called at start and by the page); silently ignores a broken saved value"""
    try:
        import store
        saved = store.kv_get("pump_cfg")
    except Exception:
        return
    if isinstance(saved, dict):
        apply(saved)
