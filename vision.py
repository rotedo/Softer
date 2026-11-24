"""Binance Vision (data.binance.vision) reader: downloads ONE day of public history on demand, works on it in memory, keeps nothing on disk.
Futures (USD-M) files: klines (1m..), aggTrades, metrics (open interest, long/short ratio; daily), monthly fundingRate.
Used by the AI tool vision_study and the /api/vision endpoint. Needs internet from the server only."""
import csv, io, urllib.error, urllib.request, zipfile
from datetime import datetime, timedelta, timezone

BASE = "https://data.binance.vision/data/futures/um"


def _get(url, timeout=40):
    req = urllib.request.Request(url, headers={"User-Agent": "orderflow-terminal/1.0"})
    try:
        return urllib.request.urlopen(req, timeout=timeout).read()
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise ValueError("no file for this coin/day on Binance Vision (not listed yet, or the day is too recent: files appear the next day)")
        raise


def _rows(raw):
    z = zipfile.ZipFile(io.BytesIO(raw))
    out = list(csv.reader(io.TextIOWrapper(z.open(z.namelist()[0]), "utf8")))
    if out and not out[0][0].replace(".", "").replace("-", "").isdigit():
        out = out[1:]  # header row
    return out


def _day(day):
    d = datetime.strptime(str(day)[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
    if d.date() >= datetime.now(timezone.utc).date():
        raise ValueError("Binance Vision daily files appear the next day: use a day before today (UTC)")
    return d


def klines(sym, day, interval="1m"):
    """list of dicts t,o,h,l,c,v,tbv (taker-buy volume) for one UTC day"""
    d = _day(day)
    sym = sym.upper()
    raw = _get(f"{BASE}/daily/klines/{sym}/{interval}/{sym}-{interval}-{d:%Y-%m-%d}.zip")
    return [{"t": int(r[0]), "o": float(r[1]), "h": float(r[2]), "l": float(r[3]), "c": float(r[4]), "v": float(r[7]), "tbv": float(r[10]), "n": int(r[8])} for r in _rows(raw)]


def metrics(sym, day):
    """open interest and long/short ratios (5-minute rows) for one UTC day, or [] if the file is missing"""
    d = _day(day)
    sym = sym.upper()
    try:
        raw = _get(f"{BASE}/daily/metrics/{sym}/{sym}-metrics-{d:%Y-%m-%d}.zip")
    except ValueError:
        return []
    return [{"ts": r[0], "oi_usd": float(r[2] or 0), "ls_top": float(r[4] or 0), "ls_all": float(r[6] or 0), "taker_ls": float(r[7] or 0)} for r in _rows(raw) if len(r) >= 8]


def pump_study(sym, day, before_h=6):
    """finds the biggest rise inside that UTC day and measures what the market did BEFORE it:
    volume build-up, range squeeze, buyer share, open-interest change. Everything comes from the downloaded files."""
    d = _day(day)
    k = klines(sym, day) + []
    try:
        k = klines(sym, (d - timedelta(days=1)).strftime("%Y-%m-%d")) + k
    except ValueError:
        pass
    if len(k) < 180:
        raise ValueError("not enough 1-minute candles in the files")
    W = 60  # minutes: the move is measured over one hour
    best, lo_i = (0, 0, 0), 0
    for i in range(1, len(k)):
        if k[i]["l"] < k[lo_i]["l"] and i - lo_i > W:
            lo_i = i
        elif i - lo_i > W:
            lo_i = max(range(i - W, i), key=lambda j: -k[j]["l"])
        g = k[i]["h"] / k[lo_i]["l"] - 1
        if g > best[0] and k[i]["t"] >= int(d.timestamp() * 1000):
            best = (g, lo_i, i)
    g, a, b = best
    if g < 0.03:
        return {"sym": sym, "day": str(day)[:10], "note": "no rise above 3% inside one hour that day", "best_move_pct": round(g * 100, 2)}
    pre = k[max(0, a - before_h * 60):a]
    base = k[max(0, a - 24 * 60):max(1, a - before_h * 60)] or pre

    def avg(xs, key):
        return sum(x[key] for x in xs) / max(1, len(xs))

    def rng(xs):
        return avg([{"r": (x["h"] - x["l"]) / x["c"]} for x in xs], "r")

    def buy(xs):
        v = sum(x["v"] for x in xs)
        return sum(x["tbv"] for x in xs) / v if v else None

    res = {"sym": sym, "day": str(day)[:10], "move_pct": round(g * 100, 1),
           "start_utc": datetime.fromtimestamp(k[a]["t"] / 1000, timezone.utc).strftime("%H:%M"),
           "minutes_to_top": b - a,
           f"volume_last_{before_h}h_vs_prior_day_avg": round(avg(pre, "v") / avg(base, "v"), 2) if avg(base, "v") else None,
           "range_squeeze_ratio": round(rng(pre[-60:]) / rng(base), 2) if pre and rng(base) else None,
           "buyer_share_before": None if buy(pre) is None else round(buy(pre), 3),
           "buyer_share_during_move": None if buy(k[a:b + 1]) is None else round(buy(k[a:b + 1]), 3),
           "trades_per_min_ratio": round(avg(pre[-60:], "n") / avg(base, "n"), 2) if avg(base, "n") else None}
    try:
        m = metrics(sym, day)
        if m:
            t0 = datetime.fromtimestamp(k[a]["t"] / 1000, timezone.utc).strftime("%Y-%m-%d %H:%M")
            before = [x for x in m if x["ts"] <= t0]
            if len(before) > 24:
                res["open_interest_change_pct_6h_before"] = round((before[-1]["oi_usd"] / before[-72]["oi_usd"] - 1) * 100, 1) if len(before) > 72 and before[-72]["oi_usd"] else None
    except Exception:
        pass
    res["note"] = "ratios above 1 mean MORE than normal. One coin proves nothing: study 10-20 pumps before turning this into a rule."
    return res