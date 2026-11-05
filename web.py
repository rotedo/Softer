"""Health + latency JSON API and tiny auto-refresh dashboard (stdlib only)."""
import json, sqlite3, threading, time
from urllib.parse import urlparse, parse_qs
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import collector as c

TABLES = c.TABLES
START = time.time()


def snapshot(db, state):
    t, tb = c.now(), {}
    try:
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=2)
        for n in TABLES:
            rows = con.execute(f"SELECT max(rowid) FROM {n}").fetchone()[0] or 0
            last = con.execute(f"SELECT max(ts) FROM {n}").fetchone()[0]
            tb[n] = {"rows": rows, "age_s": round((t - last) / 1000, 1) if last else None}
        for tb_name in ("ls", "klines"):  # per-venue freshness for the small tables
            tb[tb_name]["by_venue_age_s"] = {v: round((t - ts) / 1000) for v, ts in con.execute(f"SELECT venue, max(ts) FROM {tb_name} GROUP BY venue")}
        con.close()
    except Exception as e:
        tb = {"error": str(e)}
    feeds = {k: dict(v, age_s=round((t - v["last_rx"]) / 1000, 1) if v["last_rx"] else None) for k, v in c.STATS.items()}
    t1 = state.get("tier1", [])
    return {"uptime_s": int(time.time() - START), "feeds": feeds, "tables": tb, "live": bool(state.get("live")), "tier1_count": len(t1), "tier1": t1[:60]}


PAGE = """<!doctype html><meta name=viewport content="width=device-width,initial-scale=1"><title>orderflow health</title>
<style>body{font:14px monospace;background:#111;color:#ddd;padding:8px}td,th{padding:3px 8px;text-align:left}.ok{color:#4c4}.bad{color:#e55}</style>
<h3>Feeds</h3><table id=f></table><h3>Tables</h3><table id=t></table><h3 id=h></h3><div id=t1></div>
<script>
async function r(){try{const d=await (await fetch('/health')).json();
let f='<tr><th>feed<th>ok<th>lat ms<th>age s<th>msgs<th>reconn<th>err<th>last error</tr>';
for(const[k,v]of Object.entries(d.feeds)){const ok=v.age_s!==null&&v.age_s<(v.max_age_s||(v.kind=='rest'?400:30));
f+=`<tr><td>${k}<td class=${ok?'ok':'bad'}>${ok?'OK':'STALE'}<td>${v.lat_ms??'-'}<td>${v.age_s??'-'}<td>${v.msgs}<td>${v.reconnects}<td>${v.errors}<td>${(v.last_err||'').slice(0,60)}</tr>`}
document.getElementById('f').innerHTML=f;
let t='<tr><th>table<th>rows<th>last row age s</tr>';
for(const[k,v]of Object.entries(d.tables))t+=`<tr><td>${k}<td>${v.rows??v}<td>${v.age_s??'-'}</tr>`;
document.getElementById('t').innerHTML=t;
document.getElementById('h').textContent='uptime '+d.uptime_s+'s | mode: '+(d.live?'LIVE':'lite')+' (/mode?live=1 or 0) | tier1 pairs: '+d.tier1_count;
document.getElementById('t1').textContent=d.tier1.join(' ');}catch(e){}}
r();setInterval(r,2000);
</script>"""


def start_server(db, state, port):
    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path.startswith("/mode"):
                q = parse_qs(urlparse(self.path).query)
                if "live" in q:
                    state["live"] = q["live"][0] in ("1", "true", "on")
                body, ct = json.dumps({"live": bool(state.get("live"))}).encode(), "application/json"
            elif self.path.startswith("/health"):
                body, ct = json.dumps(snapshot(db, state)).encode(), "application/json"
            else:
                body, ct = PAGE.encode(), "text/html"
            self.send_response(200)
            self.send_header("Content-Type", ct)
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass
    srv = ThreadingHTTPServer(("0.0.0.0", port), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv
