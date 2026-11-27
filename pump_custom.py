"""YOUR OWN SETUPS. Write a function, put @custom("name") above it, push to GitHub (or ask Claude to write it). Nothing else to change.
 - The backtest shows it as its own row 'my_<name>' next to the built-in sensors.
 - Live, when it fires on any CoinDCX coin you get a Telegram alert "MY SETUP <name>".
Your function gets c = list of candles up to NOW (c[-1] = last closed 5m candle, c[-2] = the one before ...). It must return (True/False, "short note").
Each candle is a dict: t (time ms), o, h, l, c (prices), v (coin volume), q (volume in USDT), oi (open interest or None), fr (funding or None).
In live, oi / fr are None here (they are fetched only for the few coins that pass the main sensors); price and volume always work.
A mistake in this file is shown on the /pump page and never stops the rest."""
from pump_strategies import custom

ENABLED = False  # the example below stays silent until you set this to True


@custom("example_big_green")
def example_big_green(c):
    """example: last candle is +3% and its volume is more than 5x the average of the 20 candles before it"""
    if not ENABLED or len(c) < 22:
        return False, "off"
    avg = sum(x["q"] for x in c[-21:-1]) / 20
    up = (c[-1]["c"] / c[-1]["o"] - 1) * 100
    return up >= 3 and avg > 0 and c[-1]["q"] >= 5 * avg, f"candle {up:+.1f}%, volume {c[-1]['q'] / avg:.1f}x" if avg else "no volume"
