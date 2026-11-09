"""Aggregator: turns the raw collector tables (orderflow.db, read-only) into chart-ready data.

Pure Python, no extra packages. Everything here is READ-ONLY on orderflow.db.
Every function returns plain dicts/lists so api.py can json.dumps them.

Units: qty is always BASE coin, ts is epoch milliseconds, sym is BASE+USDT (BTCUSDT).
Footprint ladders use the same convention the UI uses: lv = [[bin, sell_qty, buy_qty], ...] and price = bin * step.
"""
import math, os, re, sqlite3, time

DB_PATH = os.environ.get("DB_PATH", "orderflow.db")
PREF = ["binance", "bybit", "okx", "bitget", "delta"]  # preferred candle / flow venues, in order
OI_VENUES = ("binance", "bybit", "okx", "bitget")  # delta is left out: its OI unit is contracts
WHALE_USD = float(os.environ.get("WHALE_USD", "50000"))


def now():
    return int(time.time() * 1000)


def odb():
    con = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True, timeout=3)
    con.row_factory = sqlite3.Row
    return con


def tf_minutes(tf):
    m = re.fullmatch(r"(\d+)([mhHdDw])", str(tf or ""))
    if not m:
        raise ValueError(f"bad timeframe {tf!r} (examples: 1m, 15m, 1H, 4H, 1D, 7m, 2h)")
    return int(m.group(1)) * {"m": 1, "h": 60, "H": 60, "d": 1440, "D": 1440, "w": 10080}[m.group(2)]


def nice_step(price, bps):
    """price-bucket width ~ `bps` basis points, snapped to 1/2/5 x 10^k (same rule as collector.nice_step)."""
    raw = price * bps / 1e4
    if raw <= 0:
        return 1.0
    base = 10 ** math.floor(math.log10(raw))
    for m in (5, 2, 1):
        if m * base <= raw:
            return m * base
    return base


# ---------------------------------------------------------------- candles
def _pick_venue(con, table, sym, since, venue=None, venues=PREF):
    if venue:
        return venue
    counts = {v: con.execute(f"SELECT count(*) FROM {table} WHERE venue=? AND sym=? AND ts>=?", (v, sym, since)).fetchone()[0] for v in venues}
    top = max(counts.values() or [0])
    if top == 0:
        return None
    for v in venues:  # first preferred venue with decent coverage
        if counts[v] >= 0.7 * top:
            return v


def _bucket_klines(rows, ms):
    out, cur = [], None
    for r in rows:
        b = r["ts"] // ms * ms
        if cur is None or cur["t"] != b:
            cur = {"t": b, "o": r["o"], "h": r["h"], "l": r["l"], "c": r["c"], "v": r["v"] or 0.0}
            out.append(cur)
        else:
            cur["h"] = max(cur["h"], r["h"])
            cur["l"] = min(cur["l"], r["l"])
            cur["c"] = r["c"]
            cur["v"] += r["v"] or 0.0
    return out


def _candles_from_flow(con, sym, since, ms, venue):
    """Approximate OHLC for timeframes below 15m: the collector stores per-minute price-level volume, not OHLC.
    high/low = top/bottom traded level, open/close = volume-weighted price of the first/last traded minute."""
    rows = con.execute("SELECT ts,px,buy_qty+sell_qty AS q FROM flow WHERE venue=? AND sym=? AND ts>=? ORDER BY ts", (venue, sym, since)).fetchall()
    mins, order = {}, []
    for r in rows:
        if r["ts"] not in mins:
            mins[r["ts"]] = []
            order.append(r["ts"])
        mins[r["ts"]].append((r["px"], r["q"] or 0.0))
    out, cur = [], None
    for t in order:
        lv = mins[t]
        q = sum(x[1] for x in lv) or 1e-12
        vw = sum(x[0] * x[1] for x in lv) / q
        hi, lo = max(x[0] for x in lv), min(x[0] for x in lv)
        b = t // ms * ms
        if cur is None or cur["t"] != b:
            cur = {"t": b, "o": vw, "h": hi, "l": lo, "c": vw, "v": q, "approx": True}
            out.append(cur)
        else:
            cur["h"], cur["l"], cur["c"] = max(cur["h"], hi), min(cur["l"], lo), vw
            cur["v"] += q
    return out


def candles(sym, tf="15m", n=300, venue=None, con=None):
    """-> {"venue", "approx", "tf", "candles": [{t,o,h,l,c,v}]} oldest first."""
    tfm = tf_minutes(tf)
    ms = tfm * 60000
    own = con is None
    con = con or odb()
    try:
        since = (now() // ms - n) * ms
        if tfm >= 15 and tfm % 15 == 0:
            v = _pick_venue(con, "klines", sym, since, venue)
            if not v:
                return {"venue": None, "approx": False, "tf": tf, "candles": []}
            rows = con.execute("SELECT ts,o,h,l,c,v FROM klines WHERE venue=? AND sym=? AND ts>=? ORDER BY ts", (v, sym, since)).fetchall()
            return {"venue": v, "approx": False, "tf": tf, "candles": _bucket_klines(rows, ms)[-n:]}
        v = _pick_venue(con, "flow", sym, since, venue)
        if not v:
            return {"venue": None, "approx": True, "tf": tf, "candles": []}
        return {"venue": v, "approx": True, "tf": tf, "candles": _candles_from_flow(con, sym, since, ms, v)[-n:]}
    finally:
        if own:
            con.close()


# ---------------------------------------------------------------- footprint / events / whales
def attach_flow(cs, sym, tf, venue=None, bps=3, con=None):
    """Adds per-candle footprint ladders and order-flow numbers (delta, cvd, buy ratio) to candles in place.
    venue=None sums every venue that has flow rows. Returns the price step used."""
    if not cs:
        return 1.0
    ms = tf_minutes(tf) * 60000
    own = con is None
    con = con or odb()
    try:
        step = nice_step(cs[-1]["c"], bps)
        t0, t1 = cs[0]["t"], cs[-1]["t"] + ms
        q = "SELECT ts,px,sell_qty,buy_qty FROM flow WHERE sym=? AND ts>=? AND ts<?"
        args = [sym, t0, t1]
        if venue:
            q += " AND venue=?"
            args.append(venue)
        by = {}
        for r in con.execute(q, args):
            d = by.setdefault(r["ts"] // ms * ms, {})
            b = int(math.floor(r["px"] / step))
            e = d.setdefault(b, [0.0, 0.0])
            e[0] += r["sell_qty"] or 0.0
            e[1] += r["buy_qty"] or 0.0
        cvd = 0.0
        for c in cs:
            d = by.get(c["t"])
            if not d:
                c.update(lv=[], delta=None, cvd=None, bp=None, fv=0.0)
                continue
            lv = [[b, e[0], e[1]] for b, e in sorted(d.items())]
            sell, buy = sum(x[1] for x in lv), sum(x[2] for x in lv)
            cvd += buy - sell
            c.update(lv=lv, delta=buy - sell, cvd=cvd, bp=buy / (buy + sell) if buy + sell else 0.5, fv=buy + sell)
        return step
    finally:
        if own:
            con.close()


def attach_events(cs, sym, tf, con=None):
    """Flags per candle: im (imbalance), sw (+1 swept lows then reversed up, -1 swept highs then reversed down),
    mn (possible manipulation), wh/wp/wsd/wusd (whale trades). Heuristics, documented in API.md."""
    ms = tf_minutes(tf) * 60000
    avg_v = sum(c["v"] for c in cs) / len(cs) if cs else 0
    for i, c in enumerate(cs):
        d, bp = c.get("delta"), c.get("bp")
        c.update(im=0, sw=0, mn=0, wh=0)
        if bp is not None and (bp >= .75 or bp <= .25) and c["v"] >= 1.2 * avg_v:
            c["im"] = 1
        if i >= 20 and d is not None:
            hh, ll = max(x["h"] for x in cs[i - 20:i]), min(x["l"] for x in cs[i - 20:i])
            if c["l"] < ll and c["c"] > ll and d > 0:
                c["sw"] = 1
            elif c["h"] > hh and c["c"] < hh and d < 0:
                c["sw"] = -1
        body = abs(c["c"] - c["o"]) or 1e-12
        wick = (c["h"] - c["l"]) - body
        if d is not None and wick > 2.5 * body and c["v"] > 2 * avg_v and (d < 0) == (c["c"] >= c["o"]):
            c["mn"] = 1
    if not cs:
        return
    own = con is None
    con = con or odb()
    try:
        by = {}
        for r in con.execute("SELECT ts,price,qty,side FROM trades WHERE sym=? AND ts>=? AND ts<?", (sym, cs[0]["t"], cs[-1]["t"] + ms)):
            usd = (r["price"] or 0) * (r["qty"] or 0)
            if usd < WHALE_USD:
                continue
            e = by.setdefault(r["ts"] // ms * ms, {"buy": 0.0, "sell": 0.0, "pv": 0.0, "n": 0})
            e["buy" if r["side"] == "buy" else "sell"] += usd
            e["pv"] += r["price"] * usd
            e["n"] += 1
        for c in cs:
            e = by.get(c["t"])
            if e:
                tot = e["buy"] + e["sell"]
                c.update(wh=1, wp=e["pv"] / tot, wsd=1 if e["buy"] >= e["sell"] else -1, wusd=tot)
    finally:
        if own:
            con.close()


def bundle(sym, tf="15m", n=200, venue=None, flow_venue=None, bps=3):
    """Everything the chart engine needs in ONE call: candles + footprint + events + whales."""
    con = odb()
    try:
        r = candles(sym, tf, n, venue, con)
        cs = r["candles"]
        step = attach_flow(cs, sym, tf, flow_venue, bps, con)
        attach_events(cs, sym, tf, con)
        return {"sym": sym, "tf": tf, "venue": r["venue"], "approx": r["approx"], "step": step, "candles": cs}
    finally:
        con.close()


# ---------------------------------------------------------------- liquidation zones (estimated)
LEV_TIERS = [(5, .10), (10, .25), (25, .30), (50, .20), (100, .15)]  # assumed share of new open interest per leverage
MMR = .005  # assumed maintenance margin


def liq_zones(sym, hours=72, bw_bps=5, top=40):
    """ESTIMATED liquidation levels. No exchange publishes real positions, so this models them:
    every rise in open interest is treated as new positions opened at that candle's price, split long/short by the
    candle direction and spread over assumed leverage tiers; each gets a liquidation price. Falling OI shrinks all
    open levels. A level is 'swept' when a later candle trades through it; a part may remain (rem) when price only
    touched it. -> [{side,p,u,t0,t1,rem}] (u and rem in USD)."""
    con = odb()
    try:
        since = now() - hours * 3600_000
        cs = candles(sym, "15m", hours * 4 + 4, None, con)["candles"]
        if len(cs) < 3:
            return []
        rows = con.execute("SELECT ts,venue,qty,usd FROM oi WHERE sym=? AND ts>=? ORDER BY ts", (sym, since - 3600_000)).fetchall()
    finally:
        con.close()
    ms = 900_000
    latest, series, j = {}, [], 0
    for c in cs:
        end = c["t"] + ms
        while j < len(rows) and rows[j]["ts"] < end:
            r = rows[j]
            j += 1
            if r["venue"] in OI_VENUES:
                latest[r["venue"]] = r["usd"] if r["usd"] else (r["qty"] or 0) * c["c"]
        series.append(sum(latest.values()) if latest else None)
    bw = cs[-1]["c"] * bw_bps / 1e4
    zones, prev = {}, None
    out = []
    for i, c in enumerate(cs):
        oi = series[i]
        px = (c["h"] + c["l"] + c["c"]) / 3
        if prev is not None and oi is not None:
            d = oi - prev
            if d > 0:
                ret = c["c"] / c["o"] - 1
                lf = min(.8, max(.2, .5 + .3 * max(-1, min(1, ret / .004))))
                for lev, w in LEV_TIERS:
                    for side, frac in (("long", lf), ("short", 1 - lf)):
                        p = px * (1 - 1 / lev + MMR) if side == "long" else px * (1 + 1 / lev - MMR)
                        key = (side, int(round(p / bw)))
                        z = zones.get(key)
                        if z is None:
                            z = zones[key] = {"side": side, "p": key[1] * bw, "u": 0.0, "t0": c["t"], "t1": None, "rem": 0.0}
                            out.append(z)
                        z["u"] += d * frac * w
            elif d < 0 and prev > 0:
                f = min(1.0, -d / prev)
                for z in zones.values():
                    if z["t1"] is None:
                        z["u"] *= 1 - f
        prev = oi if oi is not None else prev
        for key in list(zones):
            z = zones[key]
            if z["t1"] is not None or z["t0"] >= c["t"]:
                continue
            hit = (c["l"] <= z["p"]) if z["side"] == "long" else (c["h"] >= z["p"])
            if hit:
                depth = ((z["p"] - c["l"]) if z["side"] == "long" else (c["h"] - z["p"])) / bw
                z["t1"] = c["t"]
                z["rem"] = z["u"] * max(0.0, .4 - .1 * depth)
                del zones[key]
    out = [z for z in out if z["u"] > 0]
    out.sort(key=lambda z: -z["u"])
    return out[:top]


# ---------------------------------------------------------------- gamma exposure (BTC / ETH from Deribit options)
def _ncdf_pdf(x):
    return math.exp(-.5 * x * x) / math.sqrt(2 * math.pi)


def gex(ccy="BTC"):
    """Dealer gamma by strike from the latest Deribit options snapshot. Assumption (standard, not verified): dealers are
    long calls and short puts, so calls count positive and puts negative. Units: USD of delta change per 1% move.
    -> {"spot", "levels":[{k,g}], "call_wall","put_wall","flip"} or {"levels": []} when there is no data."""
    con = odb()
    try:
        t = con.execute("SELECT max(ts) FROM options WHERE ccy=?", (ccy,)).fetchone()[0]
        if not t:
            return {"ccy": ccy, "levels": []}
        rows = con.execute("SELECT iv,oi,und,strike,expiry,cp FROM options WHERE ccy=? AND ts=?", (ccy, t)).fetchall()
    finally:
        con.close()
    by, spot = {}, 0.0
    for r in rows:
        S, K, iv, oi = r["und"], r["strike"], r["iv"], r["oi"]
        if not (S and K and iv and oi):
            continue
        T = (r["expiry"] - t) / (365 * 24 * 3600 * 1000)
        if T <= 0:
            continue
        sig = iv / 100.0 if iv > 3 else iv  # Deribit gives percent
        d1 = (math.log(S / K) + .5 * sig * sig * T) / (sig * math.sqrt(T))
        gamma = _ncdf_pdf(d1) / (S * sig * math.sqrt(T))
        g = gamma * oi * S * S * .01 * (1 if str(r["cp"]).upper().startswith("C") else -1)
        by[K] = by.get(K, 0.0) + g
        spot = S
    if not by:
        return {"ccy": ccy, "levels": []}
    ks = sorted(by)
    levels = [{"k": k, "g": by[k]} for k in ks]
    call_wall = max(ks, key=lambda k: by[k])
    put_wall = min(ks, key=lambda k: by[k])
    flip, cum = None, 0.0
    for k in ks:  # zero-gamma level: where the running net gamma changes sign
        prev = cum
        cum += by[k]
        if prev != 0 and (prev < 0) != (cum < 0):
            flip = k
            break
    return {"ccy": ccy, "ts": t, "spot": spot, "levels": levels, "call_wall": call_wall, "put_wall": put_wall, "flip": flip}


# ---------------------------------------------------------------- small readers
def _rows(sql, args=()):
    con = odb()
    try:
        return [dict(r) for r in con.execute(sql, args)]
    finally:
        con.close()


def tape(sym, n=60):
    """Latest stored trades (the collector only stores whale-size trades individually)."""
    return _rows("SELECT ts,venue,price,qty,side FROM trades WHERE sym=? ORDER BY ts DESC LIMIT ?", (sym, n))


def book(sym):
    """Latest top-of-book and depth within 10 bps per venue, plus the aggregate."""
    t = now() - 120_000
    rows = _rows("SELECT venue,ts,bid,ask,bid_depth,ask_depth,imb FROM book WHERE sym=? AND ts>=? ORDER BY ts", (sym, t))
    last = {}
    for r in rows:
        last[r["venue"]] = r
    bd = sum(r["bid_depth"] or 0 for r in last.values())
    ad = sum(r["ask_depth"] or 0 for r in last.values())
    return {"venues": list(last.values()), "bid_depth": bd, "ask_depth": ad, "imb": (bd - ad) / (bd + ad) if bd + ad else 0.0}


def futures(sym, hours=24):
    t = now() - hours * 3600_000
    return {"oi": _rows("SELECT ts,venue,qty,usd FROM oi WHERE sym=? AND ts>=? ORDER BY ts", (sym, t)),
            "funding": _rows("SELECT ts,venue,rate,mark FROM funding WHERE sym=? AND ts>=? ORDER BY ts", (sym, t))}


def sentiment(sym, hours=24):
    t = now() - hours * 3600_000
    return {"ls": _rows("SELECT ts,venue,ratio,long_pct,short_pct FROM ls WHERE sym=? AND ts>=? ORDER BY ts", (sym, t))}


# ---------------------------------------------------------------- tiers
def atr(cs, p=14):
    if len(cs) < p + 1:
        return None
    tr = [max(c["h"] - c["l"], abs(c["h"] - cs[i]["c"]), abs(c["l"] - cs[i]["c"])) for i, c in enumerate(cs[1:])]
    return sum(tr[-p:]) / p


def tier1(max_age_ms=3 * 3600_000):
    """Tier 1 = coins that passed the collector's CoinDCX depth scan recently (scan.passed = 1)."""
    rows = _rows("SELECT sym,buy_bps,sell_bps,passed,ts FROM scan WHERE venue='coindcx' AND ts>=? ORDER BY ts", (now() - max_age_ms,))
    last = {}
    for r in rows:
        last[r["sym"]] = r
    return sorted(({"sym": s, "buy_bps": r["buy_bps"], "sell_bps": r["sell_bps"]} for s, r in last.items() if r["passed"]), key=lambda x: x["sym"])


def tiers(ratio=1.5):
    """Tier 2 = Tier 1 coins whose last 4 hourly candles span at least `ratio` x ATR(14, 1H): they are moving
    more than their normal range. A rule of thumb, change it in Settings; patterns add to it in scanner.py."""
    t1 = tier1()
    out = []
    for x in t1:
        cs = candles(x["sym"], "1H", 40, "coindcx")["candles"]
        a = atr(cs)
        r = None
        if a and len(cs) >= 4:
            r = (max(c["h"] for c in cs[-4:]) - min(c["l"] for c in cs[-4:])) / a
        out.append({**x, "atr_ratio": r, "tier": 2 if (r is not None and r >= ratio) else 1})
    return out
