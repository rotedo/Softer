"""Run:  python3 test_server.py   (builds a temporary orderflow.db, needs collector.py next to it)"""
import json, os, sys, tempfile
T = tempfile.mkdtemp()
os.environ.update(DB_PATH=os.path.join(T, "of.db"), APP_DB=os.path.join(T, "app.db"), ADMIN_PASSWORD="test-password-123")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mkdb
mkdb.make(os.environ["DB_PATH"])
import api, auth, store, aggregator as a, backtester as bt, scanner

ok = 0
def check(name, cond):
    global ok
    print(("PASS " if cond else "FAIL ") + name)
    if not cond:
        sys.exit(1)
    ok += 1

def call(m, p, body=None, cookie=""):
    s, ct, b, h = api.handle(m, p, {"Cookie": cookie}, json.dumps(body).encode() if body is not None else b"", "1.2.3.4")
    return s, json.loads(b), h

# aggregator
b = a.bundle("BTCUSDT", "15m", 100)
check("bundle 15m", len(b["candles"]) == 100 and not b["approx"] and "lv" in b["candles"][-1])
check("bundle 5m approx", a.bundle("BTCUSDT", "5m", 30)["approx"])
check("liq zones", len(a.liq_zones("BTCUSDT")) > 0)
g = a.gex("BTC"); check("gex", g.get("call_wall") and g.get("put_wall"))
check("tiers", a.tiers()[0]["sym"] == "ETHUSDT")
# backtester + sandbox
check("builtin backtest", bt.run("ema")["stats"]["trades"] >= 0)
for bad in ("import os\ndef signals(c,f): return []", "def signals(c,f):\n    return [open('x')]", "def signals(c,f):\n    return [().__class__]", "def signals(c,f):\n    while True: pass"):
    try: bt.run("code", code=bad); check("sandbox blocks", False)
    except ValueError: pass
check("sandbox blocks 4 attacks", True)
check("good code runs", bt.run("code", code="def signals(c,f):\n    return [1 if f['delta'][i]>0 else 0 for i in range(len(c))]")["stats"]["trades"] > 0)
check("pattern scan", isinstance(scanner.scan_pattern([1, 2, 3, 4, 5, 6], ["15m"], 0, ["BTCUSDT"]), list))
# api + auth
check("ping open", call("GET", "/api/ping")[0] == 200)
check("401 without login", call("GET", "/api/bundle")[0] == 401)
check("wrong password", call("POST", "/api/login", {"password": "x"})[0] == 401)
s, _, h = call("POST", "/api/login", {"password": "test-password-123"})
check("login ok", s == 200); ck = h["Set-Cookie"].split(";")[0]
check("bundle via api", call("GET", "/api/bundle?sym=BTCUSDT&tf=15m&n=50", cookie=ck)[0] == 200)
check("tampered cookie rejected", call("GET", "/api/bundle", cookie="ft=" + ck[3:-1] + "0")[0] == 401)
for _ in range(5): call("POST", "/api/login", {"password": "bad"})
check("rate limit", call("POST", "/api/login", {"password": "test-password-123"})[0] == 429)
auth._FAILS.clear()
s, j, _ = call("POST", "/api/journal", {"instrument": "BTC", "pnl": 5}, ck); check("journal add", s == 200)
check("journal list", len(call("GET", "/api/journal", cookie=ck)[1]) == 1)
call("POST", "/api/drawings", {"value": [{"type": "line"}]}, ck); check("drawings kept", call("GET", "/api/drawings", cookie=ck)[1] == [{"type": "line"}])
i = call("POST", "/api/agents", {"name": "A", "work": "w", "key": "SECRETKEY1234"}, ck)[1]["id"]
r = call("GET", "/api/agents", cookie=ck)[1]
check("agent key masked", "SECRETKEY" not in json.dumps(r) and r["agents"][0]["key"].endswith("1234"))
check("backtest api", call("POST", "/api/backtest", {"strategy": "delta", "n": 200}, ck)[0] == 200)
check("backtest bad code -> 400", call("POST", "/api/backtest", {"strategy": "code", "code": "import os"}, ck)[0] == 400)
check("health", call("GET", "/api/health", cookie=ck)[0] == 200)
check("unknown 404", call("GET", "/api/nope", cookie=ck)[0] == 404)
os.environ.pop("ADMIN_PASSWORD"); store.kv_set("pw_hash", None)
check("503 without password", call("GET", "/api/bundle")[0] == 503)
print(f"\nALL {ok} CHECKS PASSED")
