"""Analysis layer on top of aggregator.py. READ-ONLY on orderflow.db, stdlib only.

chart()    -> aggregator.bundle() + `levels`: GEX walls, liquidation zones (with CONFIRMATION), volume nodes / POC,
              and reversal CONFLUENCE zones (places where several independent sources agree).
coins()    -> every coin we hold candles for (price, 24h change, volume, tier) for the coin picker.
summary()  -> a compact version of chart() for the AI (small prompts, nothing invented).
derivs()   -> latest OI / funding / long-short per venue.

Honest limits (also shown in the UI):
  * liquidation zones and GEX are model ESTIMATES (aggregator.py says how).
  * a zone is 'confirmed' only when price really traded through it AND aggressive flow / real liquidation prints followed.
  * 'score' of a reversal zone = how many independent sources agree. It is NOT a measured probability.
"""
import json, math, statistics, time, urllib.request
import aggregator as a, config

LIQ_MIN_USD = 100_000      # real liquidation prints (liqs table) near a swept zone that count as proof
AGGR_SHARE = 0.60          # aggressive side must be >= 60 % of the sweep candle's volume ...
VOL_X = 1.3                # ... and volume >= 1.3x the median 15m volume of the last 24h
TOL_BPS = 25               # evidence closer than 0.25 % is treated as one zone
VENUE_ORDER = a.PREF + ["coindcx"]
_CC = {}


def _cached(key, ttl, fn):
    t = time.time()
    hit = _CC.get(key)
    if hit and t - hit[0] < ttl:
        return hit[1]
    v = fn()
    _CC[key] = (t, v)
    return v


# ---------------------------------------------------------------- coin list
def coins(tmap=None):
    """[{sym, px, chg (24h %), qv (24h quote volume), venue, tier (0 none / 1 / 2)}] biggest volume first."""
    def build():
        con = a.odb()
        try:
            rows = con.execute("SELECT sym,venue,ts,c,qv FROM klines WHERE ts>=? ORDER BY ts", (a.now() - 26 * 3600_000,)).fetchall()
        finally:
            con.close()
        by = {}
        for r in rows:
            by.setdefault(r["sym"], {}).setdefault(r["venue"], []).append(r)
        t24, out = a.now() - 24 * 3600_000, []
        for s, vs in by.items():
            v = next((x for x in VENUE_ORDER if x in vs), next(iter(vs)))
            rs = vs[v]
            last = rs[-1]["c"]
            ref = next((r["c"] for r in rs if r["ts"] >= t24), rs[0]["c"])
            out.append({"sym": s, "px": last, "chg": (last / ref - 1) * 100 if ref else None, "venue": v,
                        "qv": sum(r["qv"] or 0 for r in rs if r["ts"] >= t24)})
        out.sort(key=lambda x: -x["qv"])
        return out
    base = _cached("coins", 60, build)
    tmap = tmap if tmap is not None else {t["sym"]: 1 for t in a.tier1()}
    wl = [b + "USDT" for b in config.watchlist()]
    out = [dict(x, tier=tmap.get(x["sym"], 0), wl=x["sym"] in wl) for x in base]
    have = {x["sym"] for x in out}
    out += [{"sym": s, "px": None, "chg": None, "qv": 0, "venue": None, "tier": tmap.get(s, 0), "wl": True} for s in wl if s not in have]  # watchlist coin with no data yet
    return out


def all_syms():
    return [c["sym"] for c in coins() if c["px"]]


# ---------------- every tradable coin (search box), even ones we collect nothing for ----------------
_UNI = {"t": 0, "d": {}}
_SRC = {
    "binance": ("https://fapi.binance.com/fapi/v1/exchangeInfo", lambda d: [x["baseAsset"] for x in d["symbols"] if x.get("quoteAsset") == "USDT" and x.get("contractType") == "PERPETUAL" and x.get("status") == "TRADING"]),
    "bybit": ("https://api.bybit.com/v5/market/instruments-info?category=linear&limit=1000", lambda d: [x["baseCoin"] for x in d["result"]["list"] if x.get("quoteCoin") == "USDT" and x.get("status") == "Trading"]),
    "okx": ("https://www.okx.com/api/v5/public/instruments?instType=SWAP", lambda d: [x["instId"].split("-")[0] for x in d["data"] if x["instId"].endswith("-USDT-SWAP") and x.get("state") == "live"]),
}


def _universe():
    """{base coin: {venues}} from the exchanges' own symbol lists. Cached 6 h (5 min after a total failure)."""
    if time.time() - _UNI["t"] < (6 * 3600 if _UNI["d"] else 300):
        return _UNI["d"]
    out = {}
    for v, (url, pick) in _SRC.items():
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "orderflow-terminal/1.0"})
            for b in pick(json.load(urllib.request.urlopen(req, timeout=8))):
                out.setdefault(b.upper(), set()).add(v)
        except Exception:
            pass
    _UNI.update(t=time.time(), d=out or _UNI["d"])
    return _UNI["d"]


def symbols(q, limit=30):
    """Search every futures coin on Binance / Bybit / OKX plus everything we store. -> [{base, sym, venues, tracked}]"""
    q = (q or "").strip().upper().replace("USDT", "")
    if not q:
        return []
    have = {c["sym"] for c in coins() if c["px"]}
    uni = {b: set(v) for b, v in _universe().items()}
    for s in have:
        uni.setdefault(s[:-4] if s.endswith("USDT") else s, set())
    hits = [b for b in uni if q in b]
    hits.sort(key=lambda b: (b != q, not b.startswith(q), len(b), b))
    return [{"base": b, "sym": b + "USDT", "venues": sorted(uni[b]), "tracked": (b + "USDT") in have} for b in hits[:limit]]


# ---------------------------------------------------------------- GEX
def _gex(sym, price):
    ccy = sym[:-4] if sym.endswith("USDT") else sym
    if ccy not in ("BTC", "ETH"):  # only Deribit options exist for these two
        return {"ccy": ccy, "available": False, "top": []}
    g = a.gex(ccy)
    if not g.get("levels"):
        return {"ccy": ccy, "available": False, "top": []}
    near = [x for x in g["levels"] if price and abs(x["k"] / price - 1) <= .12]
    top = sorted(near, key=lambda x: -abs(x["g"]))[:6]
    return {"ccy": ccy, "available": True, "ts": g.get("ts"), "spot": g.get("spot"), "call_wall": g.get("call_wall"),
            "put_wall": g.get("put_wall"), "flip": g.get("flip"), "top": [{"k": x["k"], "g": x["g"]} for x in top]}


# ---------------------------------------------------------------- liquidation zones + confirmation
def _base_vol(con, sym):
    """median traded base-volume per 15m over the last 24h (all venues summed)."""
    rows = con.execute("SELECT ts/900000 AS b, sum(buy_qty+sell_qty) AS q FROM flow WHERE sym=? AND ts>=? GROUP BY b",
                       (sym, a.now() - 24 * 3600_000)).fetchall()
    qs = [r["q"] for r in rows if r["q"]]
    return statistics.median(qs) if qs else 0.0


def confirm(con, sym, z, base):
    """Did price REALLY run through this estimated zone with aggression? Looks at the sweep candle (+ the next one for prints).
    Evidence A: aggressive flow (longs liquidated -> aggressive SELLING, shorts -> aggressive BUYING) on >= VOL_X volume.
    Evidence B: real liquidation prints (collector `liqs`) of the matching side near the zone price."""
    ms = 900_000
    t1 = z["t1"]
    r = con.execute("SELECT sum(buy_qty) b, sum(sell_qty) s FROM flow WHERE sym=? AND ts>=? AND ts<?", (sym, t1, t1 + ms)).fetchone()
    buy, sell = r["b"] or 0.0, r["s"] or 0.0
    tot = buy + sell
    bp = buy / tot if tot else None
    vx = tot / base if base else None
    ev = []
    if bp is not None and vx is not None and vx >= VOL_X:
        share = (1 - bp) if z["side"] == "long" else bp
        if share >= AGGR_SHARE:
            ev.append(f"aggressive {'selling' if z['side'] == 'long' else 'buying'} {share * 100:.0f}% at {vx:.1f}x volume")
    lq = con.execute("SELECT sum(notional) n FROM liqs WHERE sym=? AND side=? AND ts>=? AND ts<? AND price BETWEEN ? AND ?",
                     (sym, z["side"], t1, t1 + 2 * ms, z["p"] * .994, z["p"] * 1.006)).fetchone()["n"] or 0.0
    if lq >= LIQ_MIN_USD:
        ev.append(f"real {z['side']} liquidation prints ${lq / 1e6:.2f}M")
    return {"status": "confirmed" if ev else "swept", "ev": ev, "bp": bp, "vx": vx, "liq_usd": lq}


def _liq(sym, price):
    zs = a.liq_zones(sym, 72)
    if not zs:
        return []
    con = a.odb()
    try:
        base = _base_vol(con, sym)
        open_, done = [], []
        for z in zs:
            z = dict(z)
            if z["t1"] is None:
                z.update(status="open", ev=[], bp=None, vx=None, liq_usd=0.0)
                open_.append(z)
            else:
                z.update(confirm(con, sym, z, base))
                done.append(z)
    finally:
        con.close()
    out = sorted(open_, key=lambda z: -z["u"])[:10] + sorted(done, key=lambda z: -z["u"])[:12]
    return sorted(out, key=lambda z: -z["u"])


# ---------------------------------------------------------------- volume nodes (the 'walls' we really measure)
def _nodes(cs, step):
    """Traded volume by price over the visible candles. POC = busiest price, nodes = local peaks well above average.
    (The collector keeps only total book depth, not a per-price order-book ladder, so these traded-volume nodes are the real 'walls'.)"""
    prof = {}
    for c in cs:
        for b, s, q in c.get("lv") or []:
            e = prof.setdefault(b, [0.0, 0.0])
            e[0] += s
            e[1] += q
    if not prof:
        return {"poc": None, "vah": None, "val": None, "nodes": [], "profile": []}
    tot = {b: e[0] + e[1] for b, e in prof.items()}
    mean = sum(tot.values()) / len(tot)
    allv = sum(tot.values()) or 1.0
    peaks = [b for b, v in tot.items() if v >= 1.8 * mean and v >= tot.get(b - 1, 0) and v >= tot.get(b + 1, 0)]
    peaks.sort(key=lambda b: -tot[b])
    nodes = [{"p": (b + .5) * step, "share": tot[b] / allv} for b in peaks[:6]]
    bins = sorted(tot)
    pb = max(bins, key=lambda b: tot[b])            # POC = busiest price bin
    i0 = j0 = bins.index(pb)
    acc = tot[pb]
    while acc < allv * .7 and (i0 > 0 or j0 < len(bins) - 1):  # value area = 70 % of volume around the POC
        up = tot[bins[i0 - 1]] if i0 > 0 else -1
        dn = tot[bins[j0 + 1]] if j0 < len(bins) - 1 else -1
        if up >= dn:
            i0 -= 1
            acc += up
        else:
            j0 += 1
            acc += dn
    return {"poc": (pb + .5) * step, "vah": (bins[j0] + .5) * step, "val": (bins[i0] + .5) * step, "nodes": nodes,
            "profile": [[(b + .5) * step, prof[b][0], prof[b][1]] for b in bins]}


# ---------------------------------------------------------------- reversal confluence
def _zones(price, cs, gex, liq, nodes):
    if not cs or not price:
        return []
    lo, hi = min(c["l"] for c in cs) * .97, max(c["h"] for c in cs) * 1.03
    pts = []  # (price, weight, group, label)
    if gex.get("available"):
        for k, w, lab in (("call_wall", 2, "GEX call wall"), ("put_wall", 2, "GEX put wall"), ("flip", 2, "Gamma flip")):
            if gex.get(k):
                pts.append((gex[k], w, "gex", lab))
        for x in gex["top"][:4]:
            pts.append((x["k"], 1, "gex", "GEX strike"))
    for z in liq:
        if z["status"] == "confirmed":
            pts.append((z["p"], 2, "liq", "Confirmed stop-hunt level"))
        elif z["status"] == "open":
            pts.append((z["p"], 1.5 if z["u"] >= sorted((q["u"] for q in liq), reverse=True)[min(2, len(liq) - 1)] else 1, "liq",
                        "Liquidation cluster (" + z["side"] + "s)"))
    if nodes.get("poc"):
        pts.append((nodes["poc"], 1.5, "vol", "Volume POC"))
        for k, lab in (("vah", "Value area high"), ("val", "Value area low")):
            if nodes.get(k):
                pts.append((nodes[k], 1, "vol", lab))
    for n in nodes["nodes"][1:4]:
        pts.append((n["p"], 1, "vol", "Volume node"))
    for c in cs[-60:]:
        if c.get("sw"):
            pts.append((c["l"] if c["sw"] > 0 else c["h"], 1, "sweep", "Sweep " + ("low" if c["sw"] > 0 else "high")))
    pts = sorted((p for p in pts if lo <= p[0] <= hi), key=lambda p: p[0])
    groups, cur = [], []
    for p in pts:
        if cur and p[0] - cur[0][0] > cur[0][0] * TOL_BPS / 1e4:
            groups.append(cur)
            cur = []
        cur.append(p)
    if cur:
        groups.append(cur)
    out = []
    for g in groups:
        if len({x[2] for x in g}) < 2:  # need two independent kinds of evidence
            continue
        score = sum(x[1] for x in g)
        wsum = sum(x[1] for x in g)
        p = sum(x[0] * x[1] for x in g) / wsum
        out.append({"p": p, "lo": min(x[0] for x in g), "hi": max(x[0] for x in g), "score": round(score, 1),
                    "strength": "high" if score >= 5 else "medium" if score >= 3.5 else "low",
                    "side": "support" if p < price else "resistance", "kinds": sorted({x[3] for x in g})})
    return sorted(out, key=lambda z: -z["score"])[:8]


# ---------------------------------------------------------------- chart (the one call the UI makes)
def chart(sym, tf="15m", n=200):
    b = a.bundle(sym, tf, n)
    cs = b["candles"]
    for c in cs:  # pie divergence: green candle with mostly sellers (-1) / red candle with mostly buyers (+1)
        bp = c.get("bp")
        c["dv"] = 0
        if bp is not None:
            if c["c"] > c["o"] and bp <= .45:
                c["dv"] = -1
            elif c["c"] < c["o"] and bp >= .55:
                c["dv"] = 1
    price = cs[-1]["c"] if cs else None
    if not price:
        b["levels"] = {"gex": {"available": False, "top": []}, "liq": [], "nodes": {"poc": None, "vah": None, "val": None, "nodes": [], "profile": []}, "zones": []}
        return b
    gex, liq, nodes = _gex(sym, price), _liq(sym, price), _nodes(cs, b["step"])
    b["levels"] = {"gex": gex, "liq": liq, "nodes": nodes, "zones": _zones(price, cs, gex, liq, nodes)}
    return b


def _r(x, d=2):
    return None if x is None else round(x, d)


def _p(x):
    """price rounded for prompts: 2 decimals from 100 up, else 6 (keeps the AI prompt small)"""
    return None if x is None else round(x, 2 if abs(x) >= 100 else 6)


def _day_stats(sym):
    """last 24 h high / low / VWAP from stored candles ([] -> None)"""
    cs = a.candles(sym, "1H", 26)["candles"][-24:]
    if not cs:
        return None
    v = sum(c["v"] for c in cs)
    return {"high": _p(max(c["h"] for c in cs)), "low": _p(min(c["l"] for c in cs)),
            "vwap": _p(sum((c["h"] + c["l"] + c["c"]) / 3 * c["v"] for c in cs) / v) if v else None}


def summary(sym, tf="15m", n=200):
    """Compact levels from EVERY data type for the AI. Same numbers as chart(), nothing invented."""
    b = chart(sym, tf, n)
    cs, L = b["candles"], b["levels"]
    if not cs:
        return {"sym": sym, "error": "no candles collected for this coin"}
    g, nd, price = L["gex"], L["nodes"], cs[-1]["c"]
    d = lambda p: None if p is None else round((p / price - 1) * 100, 2)  # distance from price in %
    out = {"sym": sym, "tf": tf, "price": _p(price), "approx_candles": b["approx"],
           "gex": ({k: g.get(k) for k in ("call_wall", "put_wall", "flip")} | {"top_strikes": [x["k"] for x in g["top"]]}) if g["available"] else "not available (options exist only for BTC/ETH)",
           "liquidation_zones_ESTIMATED": [{"side": z["side"], "price": _p(z["p"]), "dist_pct": d(z["p"]), "usd": round(z["u"]), "status": z["status"], "evidence": z["ev"]} for z in L["liq"][:10]],
           "volume": {"poc": _p(nd.get("poc")), "vah": _p(nd.get("vah")), "val": _p(nd.get("val")), "nodes": [_p(x["p"]) for x in nd["nodes"]]},
           "last_24h": _day_stats(sym),
           "sweeps_recent": [{"t": c["t"], "level": _p(c["l"] if c["sw"] > 0 else c["h"]), "type": "lows swept, reversed up" if c["sw"] > 0 else "highs swept, reversed down"} for c in cs[-60:] if c.get("sw")][-4:],
           "whales_recent": [{"t": c["t"], "price": _p(c.get("wp")), "side": "buy" if c.get("wsd", 0) > 0 else "sell", "usd": round(c.get("wusd") or 0)} for c in cs[-60:] if c.get("wh")][-4:],
           "reversal_zones": [{"price": _p(z["p"]), "from": _p(z["lo"]), "to": _p(z["hi"]), "dist_pct": d(z["p"]), "score": z["score"], "strength": z["strength"],
                               "type": z["side"], "evidence": z["kinds"]} for z in L["zones"][:6]],
           "last_candles": [{"t": c["t"], "o": _p(c["o"]), "h": _p(c["h"]), "l": _p(c["l"]), "c": _p(c["c"]), "buy_share": _r(c.get("bp"), 2), "delta": _r(c.get("delta"), 1),
                             "hidden_selling_on_green": c["dv"] == -1, "hidden_buying_on_red": c["dv"] == 1, "sweep": c.get("sw"), "imbalance": c.get("im")} for c in cs[-6:]]}
    try:
        bk = a.book(sym)
        out["order_book_10bps"] = {"imbalance": _r(bk["imb"], 3), "bid_depth": round(bk["bid_depth"]), "ask_depth": round(bk["ask_depth"])} if bk["venues"] else "no recent book data"
    except Exception:
        pass
    try:
        dv = derivs(sym)
        out["derivatives_24h"] = {"funding_pct": {k: _r(v["rate_pct"], 4) for k, v in dv["funding"].items()}, "oi_change_pct": {k: _r(v["chg_pct"], 2) for k, v in dv["oi"].items()},
                                  "long_short_pct": {k: v["long_pct"] for k, v in dv["long_short"].items()}}
    except Exception:
        pass
    return out


def scan(syms, tf="15m", cap=25):
    """Quick comparison of many coins (server side, no AI): where is something happening right now? Most interesting first."""
    if syms == "all" or syms is None:
        syms = all_syms()
    rows = []
    for s in list(syms)[:cap]:
        try:
            b = chart(s, tf, 80)
        except Exception:
            continue
        cs, L = b["candles"], b["levels"]
        if not cs:
            continue
        price, t6 = cs[-1]["c"], a.now() - 6 * 3600_000
        bps = [c["bp"] for c in cs[-4:] if c.get("bp") is not None]
        bs = sum(bps) / len(bps) if bps else None
        z = min(L["zones"], key=lambda q: abs(q["p"] / price - 1)) if L["zones"] else None
        zd = round((z["p"] / price - 1) * 100, 2) if z else None
        conf = [q for q in L["liq"] if q["status"] == "confirmed" and (q["t1"] or 0) >= t6]
        opn = min((q for q in L["liq"] if q["status"] == "open"), key=lambda q: abs(q["p"] / price - 1), default=None)
        sweep = any(c.get("sw") for c in cs[-6:])
        hid = any(c.get("dv") for c in cs[-3:])
        score = (2 if conf else 0) + (z["score"] if z and abs(zd) <= 1 else 0) + (1 if sweep else 0) + (1 if hid else 0) + (1 if bs is not None and abs(bs - .5) >= .15 else 0)
        rows.append({"sym": s, "price": _p(price), "buy_share_last4": _r(bs, 2), "sweep_last6": sweep, "hidden_flow_last3": hid, "confirmed_stophunt_6h": len(conf),
                     "nearest_reversal_zone": {"price": _p(z["p"]), "dist_pct": zd, "score": z["score"], "type": z["side"]} if z else None,
                     "nearest_open_liq": {"side": opn["side"], "price": _p(opn["p"]), "dist_pct": round((opn["p"] / price - 1) * 100, 2), "usd": round(opn["u"])} if opn else None,
                     "has_order_flow": bool(bps), "interest": round(score, 1)})
    return sorted(rows, key=lambda r: -r["interest"])


def derivs(sym, hours=24):
    """latest open interest (+change), funding and long/short ratio per venue."""
    f, s = a.futures(sym, hours), a.sentiment(sym, hours)
    oi = {}
    for r in f["oi"]:
        v = oi.setdefault(r["venue"], {"first": r["usd"] or r["qty"], "last": None})
        v["last"] = r["usd"] or r["qty"]
    fund = {}
    for r in f["funding"]:
        fund[r["venue"]] = {"rate_pct": (r["rate"] or 0) * 100, "mark": r["mark"]}
    ls = {}
    for r in s["ls"]:
        ls[r["venue"]] = {"ratio": r["ratio"], "long_pct": r["long_pct"], "short_pct": r["short_pct"]}
    return {"sym": sym, "hours": hours,
            "oi": {k: {"last": v["last"], "chg_pct": ((v["last"] / v["first"] - 1) * 100) if v["first"] else None} for k, v in oi.items()},
            "funding": fund, "long_short": ls}
