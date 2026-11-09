"""Pattern scan (Pearson on 32 normalised points), Tier 2 flags, rule-based setups."""
import math
import aggregator as a


def _norm(xs):
    lo, hi = min(xs), max(xs)
    return [(x - lo) / (hi - lo) if hi > lo else 0.5 for x in xs]


def pearson(x, y):
    n = len(x)
    mx, my = sum(x) / n, sum(y) / n
    sx = math.sqrt(sum((i - mx) ** 2 for i in x))
    sy = math.sqrt(sum((i - my) ** 2 for i in y))
    return 0.0 if sx == 0 or sy == 0 else sum((i - mx) * (j - my) for i, j in zip(x, y)) / (sx * sy)


def scan_pattern(points, tfs=("15m",), min_match=70, syms=None):
    """points: user-drawn shape (>=4 numbers, any scale). Returns best matches first."""
    if len(points) < 4:
        raise ValueError("need at least 4 points")
    # resample to 32 points
    n = len(points)
    pts = [points[min(n - 1, int(i * (n - 1) / 31 + .5))] for i in range(32)]
    pn = _norm(pts)
    syms = syms or [t["sym"] for t in a.tiers()] or ["BTCUSDT", "ETHUSDT"]
    out = []
    for s in syms:
        for tf in tfs:
            cs = a.candles(s, tf, 40)["candles"]
            if len(cs) < 32:
                continue
            cl = [c["c"] for c in cs[-32:]]
            m = round(max(0, pearson(pn, _norm(cl))) * 100)
            if m >= min_match:
                out.append({"sym": s, "tf": tf, "match": m, "closes": cl})
    return sorted(out, key=lambda r: -r["match"])


def suggestions(syms=None):
    """Rule-based setups: sweep reversal / imbalance with trend. SL 0.8 %, TP 2 % (as in the UI)."""
    out = []
    for s in syms or ["BTCUSDT", "ETHUSDT"]:
        try:
            b = a.bundle(s, "15m", 60)
        except Exception:
            continue
        cs = b["candles"]
        if len(cs) < 25:
            continue
        c, score, side, why = cs[-2], 0, None, []
        if c.get("sw"):
            side = "long" if c["sw"] > 0 else "short"
            score += 2
            why.append("liquidity sweep and reversal")
        if c.get("im") and c.get("delta") is not None:
            sd = "long" if c["delta"] > 0 else "short"
            if side in (None, sd):
                side = sd
                score += 1
                why.append("order-flow imbalance")
        if side:
            e = cs[-1]["c"]
            k = 1 if side == "long" else -1
            out.append({"sym": s, "side": side, "entry": e, "sl": e * (1 - k * 0.008), "tp": e * (1 + k * 0.02),
                        "why": ", ".join(why), "score": score})
    return sorted(out, key=lambda r: -r["score"])
