"""The /pump page (phone friendly) and its small JSON routes. Same login as the app.
Tabs in one page: Download (any coin, any day), Backtest, Live scanner, Settings (all pump numbers live here)."""
import calendar, json, time
from urllib.parse import urlparse, parse_qs
import pump_config as cfg, pump_download as D, pump_live, pump_validate as V

PAGE = """<!doctype html><html lang="hi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>Pump system</title><style>
:root{--bg:#0a0d12;--card:#121826;--line:#232d40;--tx:#e8f0ff;--dim:#8f9bb3;--ac:#3d8bff;--dn:#ff4d5e}
*{box-sizing:border-box;overscroll-behavior-y:none}body{margin:0;padding:12px 12px 80px;background:var(--bg);color:var(--tx);font:15px/1.45 system-ui,sans-serif}
h2{margin:14px 0 6px;font-size:16px}.c{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:10px;margin-bottom:10px}
button{background:var(--ac);color:#fff;border:0;border-radius:10px;padding:11px 14px;font-size:15px;margin:3px 3px 3px 0}button.g{background:#2a3350}button.r{background:var(--dn)}
textarea{width:100%;background:#0d121c;color:var(--tx);border:1px solid var(--line);border-radius:8px;padding:9px;font-size:14px}input,select{background:#0d121c;color:var(--tx);border:1px solid var(--line);border-radius:8px;padding:9px;font-size:15px;margin:3px 0;max-width:100%}
input[type=number]{width:110px}input[type=checkbox]{width:20px;height:20px;vertical-align:middle}label{display:block;margin:6px 0 2px}
pre{white-space:pre-wrap;word-break:break-word;font:12px/1.4 ui-monospace,monospace;margin:6px 0 0;color:#cfe0ff;max-height:42vh;overflow:auto}.d{color:var(--dim);font-size:13px}
.row{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin:4px 0}.row span{min-width:150px}b{display:block;margin:10px 0 2px;color:#9cc2ff}
</style></head><body>
<a href="/app" style="color:#9cc2ff">← App</a>
<h2>0. Data Download (कोई भी coin, कोई भी दिन)</h2><div class="c">
<label>Coin (नाम लिखो, जैसे PEPE)</label><input id="sym" list="cl" oninput="coins(this.value)" placeholder="PEPEUSDT" autocomplete="off"><datalist id="cl"></datalist>
<label>पंप वाला दिन (UTC)</label><input id="day" type="date">
<div class="row"><span>कितने दिन पहले से</span><input id="bef" type="number" value="5" min="0" step="1"></div>
<div class="row"><span>कितने दिन बाद तक</span><input id="aft" type="number" value="2" min="0" step="1"></div>
<label>Candle size</label><select id="iv"><option>1m</option><option>3m</option><option selected>5m</option><option>15m</option><option>30m</option><option>1h</option><option>4h</option><option>1d</option></select>
<label><input type="checkbox" id="oi" checked> Open Interest (सिर्फ़ पिछले 30 दिन का मिलता है)</label>
<label><input type="checkbox" id="fr" checked> Funding rate</label>
<button onclick="dl()">⬇ Download CSV</button><div id="dls" class="d"></div></div>
<h2>1. Backtest (पुराना डेटा)</h2><div class="c">
<div class="d">अपने coins खुद डालो (हर लाइन: COIN 2026-11-12, यानी coin और पंप का दिन), या नीचे से अपने-आप खोजवाओ।</div>
<label>Group A (टेस्ट वाले ~20 coins)</label><textarea id="ga" rows="5" placeholder="PEPE 2026-11-12"></textarea><button class="g" onclick="saveG('a')">Save A</button>
<label>Group B (बाद वाले नए coins)</label><textarea id="gb" rows="4" placeholder="WIF 2026-11-05"></textarea><button class="g" onclick="saveG('b')">Save B</button><div id="gm" class="d"></div>
<button onclick="run('find')">1) Pumped coins खोजो</button><button onclick="run('a')">2) Group A टेस्ट</button>
<button onclick="run('b')">3) Group B जाँच</button><button class="g" onclick="run('clean')">Raw data हटाओ</button>
<div id="st" class="d"></div><pre id="log"></pre></div>
<h2>नतीजा</h2><div class="c"><button class="g" onclick="res('a')">Group A</button><button class="g" onclick="res('b')">Group B</button><pre id="res"></pre></div>
<h2>2. Live scanner</h2><div class="c"><div id="lv" class="d"></div>
<button onclick="live(1)">ON</button><button class="r" onclick="live(0)">OFF</button><b>Alerts</b><pre id="rc"></pre><b>Watch list (अपने-आप: जिन coins में सेंसर दिखा)</b><pre id="wl"></pre><div id="cu" class="d"></div></div>
<h2>3. Settings (सारे पंप नंबर यहीं)</h2><div class="c"><div id="set"></div>
<button onclick="saveSet()">Save</button><button class="g" onclick="resetSet()">Default पर लौटाओ</button><div id="sm" class="d"></div></div>
<script>
const $=i=>document.getElementById(i);
const HINT={pct:'पंप = कितना % उछाल',window:'कितनी candles में (5m x)',hit_pct:'alert सही = इतना % ऊपर गया',horizon:'कितनी candles तक देखो',cooldown:'alert के बाद इतनी candles चुप',lookback:'strategy को कितनी पुरानी candles दिखें',volume_multiplier:'volume औसत का कितना गुना',base_candles:'औसत कितनी candles का',min_buy_ratio:'खरीदार कम से कम (0-1)',min_return_pct:'कम से कम % बढ़त',bars:'कितनी candles',breakout_candles:'कितनी पुरानी high तोड़े',oi_change_percent:'OI कितना % बढ़े',min_price_pct:'साथ में price कम से कम %',negative_below:'funding इससे नीचे',positive_above:'funding इससे ऊपर',MIN_STRATEGIES:'कम से कम कितनी strategies एक साथ',min_quote_vol_24h:'24h volume कम से कम ($)',cooldown_min:'live: एक coin का अगला alert (मिनट)',enabled:'चालू',days:'पिछले कितने दिन में खोजो',min_day_gain:'दिन में कम से कम % उछाल',group_a:'Group A कितने coins',group_b:'Group B कितने coins',before_days:'पंप से पहले के दिन',after_days:'पंप के बाद के दिन',workers:'एक साथ requests',klines:'live: कितनी candles',delay_s:'candle बंद होने के बाद सेकंड'};
async function j(u){const r=await fetch(u);if(r.status==401){location.href='/app';return null}return r.json()}
async function coins(q){if(q.length<2)return;const d=await j('/pump/coins?q='+encodeURIComponent(q));if(d)$('cl').innerHTML=d.coins.map(c=>'<option value="'+c+'">').join('')}
async function dl(){const s=$('sym').value.trim().toUpperCase(),d=$('day').value;if(!s||!d){$('dls').textContent='coin और दिन चुनो';return}
$('dls').textContent='डाउनलोड हो रहा है... (कुछ सेकंड से 1 मिनट)';
const u='/pump/download?sym='+s+'&day='+d+'&before='+$('bef').value+'&after='+$('aft').value+'&iv='+$('iv').value+'&oi='+($('oi').checked?1:0)+'&fr='+($('fr').checked?1:0);
try{const r=await fetch(u);if(r.status==401){location.href='/app';return}if(!r.ok){$('dls').textContent='❌ '+(await r.json()).error;return}
const b=await r.blob(),a=document.createElement('a');a.href=URL.createObjectURL(b);a.download=s+'_'+d+'_'+$('iv').value+'.csv';document.body.appendChild(a);a.click();a.remove();$('dls').textContent='✅ फ़ाइल डाउनलोड हो गई ('+Math.round(b.size/1024)+' KB)'}catch(e){$('dls').textContent='❌ '+e}}
async function loadG(){for(const g of['a','b']){const d=await j('/pump/group?g='+g);if(d)$('g'+g).value=d.text}}
async function saveG(g){const d=await j('/pump/group/save?g='+g+'&text='+encodeURIComponent($('g'+g).value));if(d)$('gm').textContent=d.errors.length?'❌ '+d.errors.join(' | '):'✅ Group '+g.toUpperCase()+' save हो गया'}
async function run(a){const d=await j('/pump/run?action='+a);if(d&&!d.ok)alert(d.error);tick()}
async function res(g){const d=await j('/pump/result?g='+g);if(d)$('res').textContent=d.text}
async function live(v){await j('/pump/live?on='+v);tick()}
async function tick(){const d=await j('/pump/status');if(!d)return;const s=d.validate,l=d.live;
$('st').textContent=(s.running?'चल रहा है: '+s.running:'खाली')+' | groups: '+(s.groups?'हाँ':'नहीं');
$('log').textContent=(s.log||[]).join('\\n')+(s.last?'\\n\\n'+s.last:'');
$('lv').textContent='Live: '+(l.on?'ON':'OFF')+' | cycles '+l.cycles+' | coins '+l.coins+' | caught '+l.caught+' | last cycle '+(l.last_cycle_s??'-')+'s'+(l.last_error?' | error: '+l.last_error:'');
$('wl').textContent=(l.watch||[]).map(w=>w.sym+'  '+w.since_min+' min  '+w.sensors.join('+')+(w.alerted?'  ALERTED':'')).join('\\n')||'खाली';$('cu').textContent=(l.custom&&l.custom.length?'मेरे setups: '+l.custom.join(', '):'मेरे setups: कोई नहीं')+(l.custom_error?' | ❌ '+l.custom_error:'');
$('rc').textContent=(l.recent||[]).map(a=>new Date(a.ts).toLocaleTimeString()+' '+a.sym+' '+a.score+'/100 @'+a.price).join('\\n')}
let CF={};
function walk(o,p){let h='';for(const[k,v]of Object.entries(o)){const path=p.concat(k).join('.');
if(v!==null&&typeof v==='object'){h+='<b>'+k+'</b>'+walk(v,p.concat(k))}
else{const hint=HINT[k]||'';h+='<div class="row"><span>'+k+'<br><small class="d">'+hint+'</small></span>'+(typeof v==='boolean'?'<input type="checkbox" data-p="'+path+'" '+(v?'checked':'')+'>':'<input type="number" step="any" data-p="'+path+'" value="'+v+'">')+'</div>'}}return h}
async function loadSet(){const d=await j('/pump/settings');if(!d)return;CF=d.cfg;$('set').innerHTML=walk(CF,[])}
async function saveSet(){const o={};document.querySelectorAll('#set input').forEach(i=>{const p=i.dataset.p.split('.');let t=o;for(let n=0;n<p.length-1;n++)t=t[p[n]]=t[p[n]]||{};t[p[p.length-1]]=i.type==='checkbox'?i.checked:i.value});
const d=await j('/pump/settings/save?json='+encodeURIComponent(JSON.stringify(o)));if(d)$('sm').textContent=d.errors.length?'❌ '+d.errors.join(' | '):'✅ Save हो गया';loadSet()}
async function resetSet(){await j('/pump/settings/reset');$('sm').textContent='Default लौटा दिए';loadSet()}
$('day').value=new Date(Date.now()-864e5).toISOString().slice(0,10);
tick();loadSet();loadG();setInterval(tick,4000);
</script></body></html>"""

_COINS = {"t": 0, "syms": []}


def _coins(q):
    if time.time() - _COINS["t"] > 3600 or not _COINS["syms"]:
        _COINS["syms"], _COINS["t"] = D.usdt_symbols(), time.time()
    q = q.upper().strip()
    return [s for s in _COINS["syms"] if q in s][:20]


def _download(q):
    g = lambda k, d="": (q.get(k) or [d])[0]
    sym, day, iv = g("sym").upper().strip(), g("day"), g("iv", "5m")
    if not sym.isalnum() or iv not in D.IV:
        return {"error": "coin या candle size सही नहीं"}
    try:
        t0 = calendar.timegm(time.strptime(day, "%Y-%m-%d")) * 1000
        before, after = float(g("before", "5")), float(g("after", "2"))
    except ValueError:
        return {"error": "दिन या संख्या सही नहीं (दिन: साल-महीना-तारीख)"}
    if before < 0 or after < 0 or before + after > 31:
        return {"error": "कुल 31 दिन से ज़्यादा नहीं (पहले + बाद)"}
    rows = D.fetch(sym, int(t0 - before * D.DAY), int(t0 + (after + 1) * D.DAY), iv, g("oi", "1") == "1", g("fr", "1") == "1")
    if not rows:
        return {"error": f"{sym} का इस समय का डेटा नहीं मिला (coin का नाम या तारीख जाँचो)"}
    return {"csv": D.to_csv(rows), "name": f"{sym}_{day}_{iv}.csv"}


def handle(path, headers):
    """-> (status, content_type, bytes, extra_headers)"""
    import api
    J = "application/json"
    cfg.load_saved()
    u = urlparse(path)
    if not api.auth.valid(api._cookie(headers)):
        if u.path == "/pump":
            return 401, "text/html; charset=utf-8", "<meta name=viewport content='width=device-width'><body style='font:16px sans-serif;padding:20px'>पहले <a href='/app'>/app</a> में login करो, फिर यह पेज दोबारा खोलो।".encode(), {}
        return 401, J, b'{"error": "login required (open /app first)"}', {}
    q = parse_qs(u.query)
    js = lambda o, code=200: (code, J, json.dumps(o, default=str).encode(), {})
    try:
        if u.path == "/pump/status":
            return js({"validate": V.status(), "live": pump_live.status()})
        if u.path == "/pump/run":
            a = (q.get("action") or [""])[0]
            return js(V.start(a) if a in ("find", "a", "b", "clean") else {"ok": False, "error": "unknown action"})
        if u.path == "/pump/result":
            g = (q.get("g") or ["a"])[0]
            return js({"text": V.saved_text(g if g in ("a", "b") else "a") + ("\n\n" + V.compare() if g == "b" else "")})
        if u.path == "/pump/live":
            pump_live.set_on((q.get("on") or ["0"])[0] in ("1", "true", "on"))
            return js(pump_live.status())
        if u.path == "/pump/coins":
            return js({"coins": _coins((q.get("q") or [""])[0])})
        if u.path == "/pump/download":
            r = _download(q)
            if "error" in r:
                return js(r, 400)
            return 200, "text/csv; charset=utf-8", r["csv"].encode(), {"Content-Disposition": f'attachment; filename="{r["name"]}"'}
        if u.path == "/pump/group":
            return js({"text": V.group_text((q.get("g") or ["a"])[0])})
        if u.path == "/pump/group/save":
            return js({"errors": V.set_group((q.get("g") or ["a"])[0], (q.get("text") or [""])[0])})
        if u.path == "/pump/settings":
            return js({"cfg": cfg.snapshot()})
        if u.path == "/pump/settings/save":
            try:
                new = json.loads((q.get("json") or ["{}"])[0])
            except ValueError:
                return js({"errors": ["bad data"]})
            return js({"errors": cfg.save(new)})
        if u.path == "/pump/settings/reset":
            cfg.reset()
            return js({"ok": True})
    except Exception as e:  # network / Binance problems show as a message, never a crash
        return js({"error": f"{type(e).__name__}: {e}"[:200]}, 500)
    return 200, "text/html; charset=utf-8", PAGE.encode(), {}
