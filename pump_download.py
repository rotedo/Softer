"""Binance Futures PUBLIC API (no key): symbols, daily scan for pumped coins, candles + open interest + funding for any window.
Raw data is only a temporary box on disk (csv.gz) and is deleted by cleanup(). Nothing here sees live money or places orders.
HTTP is a plain function so tests can replace it."""
import csv, glob, gzip, io, json, os, time, urllib.error, urllib.parse, urllib.request
import pump_config as cfg

BASE = "https://fapi.binance.com"
DAY = 86_400_000
IV = {"1m": 60_000, "3m": 180_000, "5m": 300_000, "15m": 900_000, "30m": 1_800_000, "1h": 3_600_000, "4h": 14_400_000, "1d": DAY}
OI_IV = {"5m", "15m", "30m", "1h", "4h", "1d"}  # periods Binance offers for open-interest history
COLS = ["t", "o", "h", "l", "c", "v", "q", "n", "tb", "oi", "fr"]


def HTTP(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 pump-system"})
    try:
        return json.load(urllib.request.urlopen(req, timeout=30))
    except urllib.error.HTTPError as e:
        if e.code in (451, 403):
            raise RuntimeError(f"Binance refuses this server's country (HTTP {e.code}); the server must be outside the US")
        if e.code in (418, 429):
            raise TimeoutError(f"Binance rate limit (HTTP {e.code})")
        try:
            msg = json.loads(e.read()).get("msg", "")
        except Exception:
            msg = ""
        raise RuntimeError(f"Binance HTTP {e.code}: {msg}"[:160])


def _get(path, **params):
    url = BASE + path + ("?" + urllib.parse.urlencode(params) if params else "")
    for n in range(4):
        try:
            return HTTP(url)
        except (TimeoutError, urllib.error.URLError, OSError) as e:
            if n == 3:
                raise RuntimeError(f"network problem: {e}")
            time.sleep(1.5 * (n + 1))


def usdt_symbols():
    d = _get("/fapi/v1/exchangeInfo")
    return sorted(s["symbol"] for s in d["symbols"] if s.get("quoteAsset") == "USDT" and s.get("contractType") == "PERPETUAL" and s.get("status") == "TRADING")


def find_pumps(progress=print):
    """coins whose best CLOSED day in the last FIND.days days gained >= FIND.min_day_gain % (high vs open). -> [{sym, day_ms, gain}]"""
    f, now = cfg.FIND, int(time.time() * 1000)
    syms, out = usdt_symbols(), []
    for n, s in enumerate(syms, 1):
        try:
            ks = _get("/fapi/v1/klines", symbol=s, interval="1d", limit=f["days"] + 1)
        except RuntimeError as e:
            if "refuses" in str(e):
                raise
            continue
        best = None
        for k in ks:
            t, o, h = int(k[0]), float(k[1]), float(k[2])
            if t + DAY > now or t < now - f["days"] * DAY or o <= 0:
                continue
            g = (h / o - 1) * 100
            if g >= f["min_day_gain"] and (best is None or g > best["gain"]):
                best = {"sym": s, "day_ms": t, "gain": round(g, 1)}
        if best:
            out.append(best)
        if n % 100 == 0:
            progress(f"scanned {n}/{len(syms)} coins, {len(out)} pumped so far")
        time.sleep(0.03)
    return out


def _paged(path, key_t, step, start, end, limit, **params):
    rows, t = [], start
    while t < end:
        page = _get(path, startTime=int(t), endTime=int(end), limit=limit, **params)
        if not page:
            break
        rows += page
        last = key_t(page[-1])
        if len(page) < limit or last + step <= t:
            break
        t = last + step
    return rows


def fetch(sym, start, end, interval="5m", oi=True, fr=True):
    """candle dicts {t,o,h,l,c,v,q,n,tb,oi,fr} for [start, end) ms. oi = USD open interest (None where Binance has no history), fr = last funding rate."""
    step, now = IV[interval], int(time.time() * 1000)
    ks = _paged("/fapi/v1/klines", lambda k: int(k[0]), step, start, end, 1500, symbol=sym, interval=interval)
    seen, rows = set(), []
    for k in ks:
        t = int(k[0])
        if t in seen or t + step > now or not start <= t < end:  # no duplicates, no still-forming candle
            continue
        seen.add(t)
        rows.append({"t": t, "o": float(k[1]), "h": float(k[2]), "l": float(k[3]), "c": float(k[4]), "v": float(k[5]), "q": float(k[7]),
                     "n": int(k[8]), "tb": float(k[9]), "oi": None, "fr": None})
    rows.sort(key=lambda r: r["t"])
    if rows and oi and interval in OI_IV:
        s0 = max(start, now - 29 * DAY)  # Binance keeps only ~30 days of open-interest history
        if s0 < end:
            h = _paged("/futures/data/openInterestHist", lambda r: int(r["timestamp"]), step, s0, end, 500, symbol=sym, period=interval)
            pts = sorted((int(r["timestamp"]), float(r["sumOpenInterestValue"])) for r in h)
            _asof(rows, pts, "oi", step)
    if rows and fr:
        f = _paged("/fapi/v1/fundingRate", lambda r: int(r["fundingTime"]), 1, start - 9 * 3_600_000, end, 1000, symbol=sym)
        pts = sorted((int(r["fundingTime"]), float(r["fundingRate"])) for r in f)
        _asof(rows, pts, "fr", None)
    return rows


def _asof(rows, pts, key, max_age):
    """put the latest point at or before each candle's time on the candle (never a later point). max_age: ignore points older than that."""
    j, last = 0, None
    for r in rows:
        while j < len(pts) and pts[j][0] <= r["t"] + (max_age or 0) - 1:
            last = pts[j]
            j += 1
        if last and (max_age is None or r["t"] - last[0] <= 3 * max_age):
            r[key] = last[1]


def fetch_pump_window(sym, day_ms):
    w = cfg.WINDOW
    return fetch(sym, day_ms - w["before_days"] * DAY, day_ms + (w["after_days"] + 1) * DAY, "5m", True, True)


def to_csv(rows):
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["time_utc"] + COLS)
    for r in rows:
        w.writerow([time.strftime("%Y-%m-%d %H:%M", time.gmtime(r["t"] / 1000))] + ["" if r.get(c) is None else r[c] for c in COLS])
    return out.getvalue()


def _path(sym):
    os.makedirs(cfg.DATA_DIR, exist_ok=True)
    return os.path.join(cfg.DATA_DIR, f"{sym}.csv.gz")


def save(sym, rows):
    with gzip.open(_path(sym), "wt", newline="") as f:
        f.write(to_csv(rows))


def load(sym):
    try:
        with gzip.open(_path(sym), "rt", newline="") as f:
            rd = csv.DictReader(f)
            return [{c: (None if r[c] == "" else (int(r[c]) if c in ("t", "n") else float(r[c]))) for c in COLS} for r in rd]
    except (OSError, ValueError, KeyError):
        return None


def cleanup():
    """delete the temporary raw data (keeps groups.json / result files). -> number of files deleted"""
    n = 0
    for f in glob.glob(os.path.join(cfg.DATA_DIR, "*.csv.gz")) + glob.glob(os.path.join(cfg.DATA_DIR, "*.parquet")):
        try:
            os.remove(f)
            n += 1
        except OSError:
            pass
    return n
