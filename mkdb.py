"""synthetic orderflow.db for tests"""
import sqlite3, random, math, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
def make(path, n15=300, seed=1):
    import collector as c
    if os.path.exists(path): os.remove(path)
    con = sqlite3.connect(path)
    for s in c.SCHEMA: con.execute(s)
    r = random.Random(seed)
    now = int(time.time()*1000); ms = 15*60000
    t0 = (now//ms - n15)*ms
    px = 60000.0
    for i in range(n15):
        ts = t0 + i*ms
        o = px; px *= 1 + r.gauss(0, 0.004); cl = px
        h = max(o, cl)*(1+abs(r.gauss(0, .0015))); l = min(o, cl)*(1-abs(r.gauss(0, .0015)))
        for v in ("binance", "bybit"):
            con.execute("INSERT INTO klines VALUES(?,?,?,?,?,?,?,?,?,?,?)", (ts, v, "BTCUSDT", o, h, l, cl, 100, 6e6, 500, 50))
        for v in ("binance", "bybit", "okx", "bitget"):
            con.execute("INSERT INTO oi VALUES(?,?,?,?,?)", (ts+1000, v, "BTCUSDT", 1000+i*r.uniform(-3, 8), (1000+i*3)*cl))
        for m in range(15):
            tm = ts + m*60000
            for k in range(6):
                p = round(l + (h-l)*r.random(), -1)
                con.execute("INSERT OR REPLACE INTO flow VALUES(?,?,?,?,?,?,?,?,?,?,?)", (tm, "binance", "BTCUSDT", p, 10, r.random()*3, r.random()*3, 0, 0, 5, 5))
        if i % 7 == 0:
            con.execute("INSERT INTO trades VALUES(?,?,?,?,?,?,?,?)", (ts+5000, "binance", "perp", "BTCUSDT", cl, 2.0, r.choice(["buy", "sell"]), f"t{i}"))
        con.execute("INSERT INTO book VALUES(?,?,?,?,?,?,?,?)", (ts+2000, "binance", "BTCUSDT", cl-1, cl+1, 5e5, 6e5, -0.09))
        con.execute("INSERT INTO funding VALUES(?,?,?,?,?,?,?)", (ts+2000, "binance", "BTCUSDT", 0.0001, cl, cl, ts+ms))
        con.execute("INSERT INTO ls VALUES(?,?,?,?,?,?)", (ts+2000, "binance", "BTCUSDT", 1.2, 55, 45))
    # hourly klines for tier test (coindcx tier1 coin ETHUSDT)
    con.execute("INSERT INTO scan VALUES(?,?,?,?,?,?,?)", (now-1000, "coindcx", "ETHUSDT", 1e8, 3, 4, 1))
    p = 3000.0
    for i in range(160):
        ts = (now//ms - 160 + i)*ms; o = p; p *= 1+r.gauss(0, .003)
        con.execute("INSERT INTO klines VALUES(?,?,?,?,?,?,?,?,?,?,?)", (ts, "coindcx", "ETHUSDT", o, max(o, p)*1.001, min(o, p)*.999, p, 10, 3e4, 50, 5))
    # options
    exp = now + 7*86400000
    for k in range(50000, 70001, 2000):
        for cp in "CP":
            con.execute("INSERT INTO options VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", (now-5000, "deribit", "BTC", f"BTC-X-{k}-{cp}", 55.0, .01, r.uniform(10, 500), 1, 60000, k, exp, cp))
    con.commit(); con.close()
if __name__ == "__main__":
    make(sys.argv[1] if len(sys.argv) > 1 else "/tmp/of.db")
