"""Runs the whole backtest plan. From the /pump page (phone) or from a PC terminal:
   python pump_validate.py find    -> find recently pumped coins, split into group A (25) and group B (60, untouched until validation)
   python pump_validate.py a       -> download group A, backtest every strategy, print the table
   python pump_validate.py b       -> same settings on group B (overfitting check, compared with A)
   python pump_validate.py clean   -> delete the temporary raw data"""
import json, os, random, sys, threading, time
import pump_config as cfg
import pump_download as D
import pump_engine as E

STATE = {"running": None, "log": [], "last": ""}
_LOCK = threading.Lock()


def log(msg):
    STATE["log"] = (STATE["log"] + [time.strftime("%H:%M:%S ") + str(msg)])[-60:]
    print(msg, flush=True)


def _file(name):
    os.makedirs(cfg.DATA_DIR, exist_ok=True)
    return os.path.join(cfg.DATA_DIR, name)


def _read(name):
    try:
        return json.load(open(_file(name)))
    except (OSError, ValueError):
        return None


def groups():
    return _read("groups.json")


def set_group(g, text):
    """you pick the coins: one per line, 'PEPE 2026-11-12' (coin, exact pump day UTC). -> list of problems (empty = saved)"""
    import calendar
    coins, bad = [], []
    for ln in str(text).replace(",", "\n").splitlines():
        p = ln.split()
        if not p:
            continue
        try:
            s = p[0].upper()
            s = s if s.endswith("USDT") else s + "USDT"
            coins.append({"sym": s, "day_ms": calendar.timegm(time.strptime(p[1], "%Y-%m-%d")) * 1000, "gain": 0})
        except (IndexError, ValueError):
            bad.append(ln.strip()[:40])
    if bad:
        return ["line not understood (write: COIN YYYY-MM-DD): " + " | ".join(bad)]
    if g not in ("a", "b"):
        return ["group must be a or b"]
    gr = groups() or {"at": int(time.time()), "a": [], "b": []}
    gr[g] = coins
    json.dump(gr, open(_file("groups.json"), "w"))
    for c in coins:  # new pump day for a coin: old downloaded file would be wrong
        for ext in ("parquet", "csv.gz"):
            f = _file(f"{c['sym']}.{ext}")
            os.path.exists(f) and os.remove(f)
    return []


def group_text(g):
    gr = groups() or {}
    return "\n".join(f"{c['sym']} {time.strftime('%Y-%m-%d', time.gmtime(c['day_ms'] / 1000))}" for c in gr.get(g, []))


def step_find():
    log("looking for pumped coins on Binance (takes a few minutes)...")
    found = D.find_pumps(progress=log)
    random.Random(1).shuffle(found)  # shuffled, so group A is not just the strongest pumps
    a, b = found[:cfg.FIND["group_a"]], found[cfg.FIND["group_a"]:cfg.FIND["group_a"] + cfg.FIND["group_b"]]
    json.dump({"at": int(time.time()), "a": a, "b": b}, open(_file("groups.json"), "w"))
    msg = f"found {len(found)} pumped coins -> group A {len(a)}, group B {len(b)}"
    log(msg)
    return msg


def step_test(g):
    gr = groups()
    if not gr:
        return "first run: find"
    coins, results = gr[g], []
    if not coins:
        return f"group {g.upper()} is empty (not enough pumped coins found)"
    for n, c in enumerate(coins, 1):
        sym = c["sym"]
        try:
            cs = D.load(sym)
            if not cs:
                log(f"[{n}/{len(coins)}] downloading {sym}")
                cs = D.fetch_pump_window(sym, c["day_ms"])
                D.save(sym, cs)
            if len(cs) < E.WARMUP + 50:
                log(f"{sym}: too little data, skipped")
                continue
            results.append(E.run_coin(cs))
        except Exception as e:
            log(f"{sym}: failed ({e})")
    rows = E.aggregate(results)
    snap = {"group": g, "coins_tested": len(results), "at": int(time.time()), "strategy_config": cfg.STRATEGY_CONFIG,
            "min_strategies": cfg.MIN_STRATEGIES, "pump": cfg.PUMP, "eval": cfg.EVAL, "rows": rows}
    json.dump(snap, open(_file(f"result_{g}.json"), "w"))
    txt = E.table(rows, f"GROUP {g.upper()}: {len(results)} coins, pump = +{cfg.PUMP['pct']}% in {cfg.PUMP['window'] * 5} min, hit = +{cfg.EVAL['hit_pct']}% in {cfg.EVAL['horizon'] * 5 // 60}h")
    if g == "b":
        txt += "\n\n" + compare()
    log("done")
    return txt


def compare():
    a, b = _read("result_a.json"), _read("result_b.json")
    if not (a and b):
        return "run group A and group B to compare"
    if a["strategy_config"] != b["strategy_config"] or a["min_strategies"] != b["min_strategies"]:
        return "NOTE: settings changed between A and B, so this is not a clean overfitting check. Run A again with the same settings, then B."
    ra, rb = {r["view"]: r for r in a["rows"]}, {r["view"]: r for r in b["rows"]}
    lines = ["OVERFITTING CHECK (same settings, new coins):"]
    for v in ra:
        x, y = ra[v], rb.get(v)
        if not y or x["hit_pct"] is None or y["hit_pct"] is None:
            lines.append(f"- {v}: not enough alerts to compare")
            continue
        drop = x["hit_pct"] - y["hit_pct"]
        verdict = "OK, holds up" if drop <= x["hit_pct"] * 0.3 else "WEAK: likely tuned to group A"
        lines.append(f"- {v}: hit% A {x['hit_pct']} -> B {y['hit_pct']}  ({verdict})")
    return "\n".join(lines)


def start(action):
    """background run for the web page. one job at a time"""
    if not _LOCK.acquire(blocking=False):
        return {"ok": False, "error": "another job is running: " + str(STATE["running"])}

    def job():
        try:
            STATE["running"], STATE["last"] = action, ""
            STATE["last"] = step_find() if action == "find" else step_test(action) if action in ("a", "b") else f"deleted {D.cleanup()} files" if action == "clean" else "unknown"
        except Exception as e:
            STATE["last"] = f"FAILED: {e}"
            log(STATE["last"])
        finally:
            STATE["running"] = None
            _LOCK.release()
    threading.Thread(target=job, daemon=True).start()
    return {"ok": True}


def status():
    return {"running": STATE["running"], "log": STATE["log"][-15:], "last": STATE["last"], "groups": bool(groups()),
            "saved": {g: bool(_read(f"result_{g}.json")) for g in "ab"}}


def saved_text(g):
    r = _read(f"result_{g}.json")
    return E.table(r["rows"], f"GROUP {g.upper()} (saved)") if r else "no result yet"


if __name__ == "__main__":
    cmd = (sys.argv[1] if len(sys.argv) > 1 else "").lower()
    if cmd == "find":
        print(step_find())
    elif cmd in ("a", "b"):
        print(step_test(cmd))
    elif cmd == "clean":
        print("deleted", D.cleanup(), "files")
    else:
        print(__doc__)
