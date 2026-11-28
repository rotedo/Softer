"""Binance Vision (data.binance.vision) = Binance's PUBLIC data dumps. No key, no country block, works from GitHub's machines.
Gives, for any past day: 5m candles, open interest (5m, 'metrics' files, any age), taker long/short ratio, and monthly funding.
Only COMPLETE days exist (yesterday is the newest). Same candle format as pump_download.fetch: {t,o,h,l,c,v,q,n,tb,oi,fr} + tls.
GET is a plain function so tests can replace it."""
import csv, datetime as dt, io, re, urllib.error, urllib.request, zipfile
from concurrent.futures import ThreadPoolExecutor
import pump_download as D

BASE = "https://data.binance.vision/data/futures/um"
STEP = 300_000


def GET(url):
    """bytes, or None when the file does not exist (coin not listed that day / not published yet)"""
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 pump-lab"})
    for n in range(3):
        try:
            return urllib.request.urlopen(req, timeout=60).read()
        except urllib.error.HTTPError as e:
            if e.code in (403, 404):
                return None
        except OSError:
            pass
    return None


def _table(b):
    if not b:
        return []
    with zipfile.ZipFile(io.BytesIO(b)) as z:
        return list(csv.reader(io.StringIO(z.read(z.namelist()[0]).decode())))


def _day(d):
    return d.strftime("%Y-%m-%d")


def _days(a, b):
    d = a
    while d <= b:
        yield d
        d += dt.timedelta(days=1)


def _ms(s):
    return int(dt.datetime.strptime(s, "%Y-%m-%d %H:%M:%S").replace(tzinfo=dt.timezone.utc).timestamp() * 1000)


def _klines(sym, d):
    out = []
    for r in _table(GET(f"{BASE}/daily/klines/{sym}/5m/{sym}-5m-{_day(d)}.zip")):
        if not r or not r[0].isdigit():
            continue  # header line
        out.append({"t": int(r[0]), "o": float(r[1]), "h": float(r[2]), "l": float(r[3]), "c": float(r[4]), "v": float(r[5]), "q": float(r[7]),
                    "n": int(r[8]), "tb": float(r[9]), "oi": None, "fr": None, "tls": None})
    return out


def _metrics(sym, d):
    t = _table(GET(f"{BASE}/daily/metrics/{sym}/{sym}-metrics-{_day(d)}.zip"))
    if not t:
        return []
    head, out = t[0], []
    ix = {h: i for i, h in enumerate(head)}
    for r in t[1:]:
        try:
            out.append((_ms(r[ix["create_time"]]), float(r[ix["sum_open_interest_value"]]), float(r[ix["sum_taker_long_short_vol_ratio"]])))
        except (KeyError, ValueError, IndexError):
            continue
    return out


def _funding(sym, month):
    t = _table(GET(f"{BASE}/monthly/fundingRate/{sym}/{sym}-fundingRate-{month}.zip"))
    return [(int(r[0]), float(r[2])) for r in t if r and r[0].isdigit()]


def fetch(sym, d0, d1):
    """5m candles for UTC days d0..d1 (datetime.date) with open interest, taker ratio and funding. -> (rows, notes)"""
    days = list(_days(d0, d1))
    with ThreadPoolExecutor(max_workers=8) as ex:
        ks = list(ex.map(lambda d: _klines(sym, d), days))
        ms = list(ex.map(lambda d: _metrics(sym, d), days))
    rows = sorted((r for k in ks for r in k), key=lambda r: r["t"])
    notes = []
    miss = [_day(d) for d, k in zip(days, ks) if not k]
    if miss:
        notes.append(f"{sym}: no candle file for {len(miss)} day(s): {', '.join(miss[:6])}")
    if not rows:
        return rows, notes
    mt = sorted(p for m in ms for p in m)
    if mt:
        D._asof(rows, [(t, v) for t, v, _ in mt], "oi", STEP)
        D._asof(rows, [(t, x) for t, _, x in mt], "tls", STEP)
    else:
        notes.append(f"{sym}: no open-interest (metrics) files")
    months = sorted({_day(d)[:7] for d in days})
    fp = sorted(p for m in months for p in _funding(sym, m))
    if fp:
        D._asof(rows, fp, "fr", None)
    else:
        notes.append(f"{sym}: no funding file (current month is published only after it ends)")
    return rows, notes


S3 = "https://s3-ap-northeast-1.amazonaws.com/data.binance.vision"


def list_symbols():
    """every USDT perpetual that has candle files on Binance Vision (the whole futures universe, ~500)"""
    out, marker = [], ""
    while True:
        b = GET(f"{S3}?delimiter=/&prefix=data/futures/um/daily/klines/&max-keys=1000" + (f"&marker={marker}" if marker else ""))
        if not b:
            break
        text = b.decode("utf-8", "ignore")
        names = re.findall(r"<Prefix>data/futures/um/daily/klines/([^/<]+)/</Prefix>", text)
        out += names
        if "<IsTruncated>true</IsTruncated>" in text and names:
            marker = "data/futures/um/daily/klines/" + names[-1] + "/"
        else:
            break
    return sorted(n for n in set(out) if n.endswith("USDT") and "_" not in n)
