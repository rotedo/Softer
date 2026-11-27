"""Tools the in-app AI chat can use for the pump system (any AI key: Claude, Gemini, ChatGPT...). agents.py loads TOOLS and DOC.
The AI can download any coin / any pump day, set your 20 coins, change settings and start the tests. It cannot edit the Python files."""
import calendar, time
import pump_config as cfg, pump_download as D, pump_engine as E, pump_validate as V, pump_live

DOC = ("PUMP SYSTEM tools (historical Binance data; use them when the user talks about a pump day, downloading data, his pump coins, pump settings or tests): "
       "pump_data(sym,day,before,after,interval,oi,fr) downloads one coin around its EXACT pump day (day=YYYY-MM-DD UTC; before/after = days; interval 1m..1d) "
       "and returns a summary plus a download link for the user; pump_set_group(group,coins) group 'a' or 'b', coins=[{sym,day}] sets the user's own coins; "
       "pump_group(group) shows them; pump_settings() shows all pump numbers; pump_settings_set(changes) changes them (nested, e.g. {\"STRATEGY_CONFIG\":{\"volume_spike\":{\"volume_multiplier\":4}}}); "
       "pump_run(action) action a|b|find starts the backtest in the background; pump_result(group) reads the last result; pump_live(on) switches the live scanner. "
       "Ask the user for a missing coin or day instead of guessing.")


def _day(s):
    return calendar.timegm(time.strptime(str(s)[:10], "%Y-%m-%d")) * 1000


def pump_data(g, **k):
    sym = str(k.get("sym", "")).upper().replace("/", "").replace("-", "")
    sym = sym if sym.endswith("USDT") else sym + "USDT"
    day, before, after = str(k.get("day", ""))[:10], float(k.get("before", 5)), float(k.get("after", 2))
    iv = str(k.get("interval", "5m"))
    if iv not in D.IV or before < 0 or after < 0 or before + after > 31:
        return {"error": "interval must be one of " + ",".join(D.IV) + "; before+after at most 31 days"}
    t0 = _day(day)
    oi, fr = bool(k.get("oi", True)), bool(k.get("fr", True))
    rows = D.fetch(sym, int(t0 - before * D.DAY), int(t0 + (after + 1) * D.DAY), iv, oi, fr)
    if not rows:
        return {"error": f"no data for {sym} on {day}"}
    D.save(sym, rows)
    url = f"/pump/download?sym={sym}&day={day}&before={before:g}&after={after:g}&iv={iv}&oi={int(oi)}&fr={int(fr)}"
    out = {"sym": sym, "rows": len(rows), "from": time.strftime("%Y-%m-%d %H:%M", time.gmtime(rows[0]["t"] / 1000)), "to": time.strftime("%Y-%m-%d %H:%M", time.gmtime(rows[-1]["t"] / 1000)),
           "download_link_for_user": url, "note": "tell the user to open /pump > Download to get the CSV file"}
    if iv == "5m":  # pump anatomy is only meaningful on the 5m grid the pump definition uses
        pumps = E.label_pumps(rows)
        out["pumps_found"] = [{"start": time.strftime("%Y-%m-%d %H:%M", time.gmtime(rows[p["start"]]["t"] / 1000)), "gain_pct": p["gain"]} for p in pumps[:3]]
        if pumps:
            s = pumps[0]["start"]
            if s >= 60:
                base = sum(x["q"] for x in rows[s - 49:s - 1]) / 48
                out["before_first_pump"] = {"volume_vs_4h_avg_at_start": round(rows[s]["q"] / base, 1) if base else None,
                                            "price_change_prior_1h_pct": round((rows[s]["c"] / rows[s - 12]["c"] - 1) * 100, 2),
                                            "oi_change_prior_1h_pct": round((rows[s]["oi"] / rows[s - 12]["oi"] - 1) * 100, 2) if rows[s]["oi"] and rows[s - 12]["oi"] else None,
                                            "funding_rate": rows[s]["fr"]}
    return out


TOOLS = {
    "pump_data": pump_data,
    "pump_set_group": lambda g, **k: {"errors": V.set_group(str(k.get("group", "a")).lower(), "\n".join(f"{c.get('sym', '')} {c.get('day', '')}" for c in k.get("coins", []))) or "saved"},
    "pump_group": lambda g, **k: V.group_text(str(k.get("group", "a")).lower()),
    "pump_settings": lambda g, **k: cfg.snapshot(),
    "pump_settings_set": lambda g, **k: {"errors": cfg.save(k.get("changes") or {}) or "saved"},
    "pump_run": lambda g, **k: V.start(str(k.get("action", "")).lower()) if str(k.get("action", "")).lower() in ("a", "b", "find") else {"error": "action must be a, b or find"},
    "pump_result": lambda g, **k: V.saved_text(str(k.get("group", "a")).lower()) + ("\n" + V.compare() if str(k.get("group")).lower() == "b" else ""),
    "pump_live": lambda g, **k: (pump_live.set_on(bool(k.get("on"))), pump_live.status())[1],
}
