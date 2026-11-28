"""The /pump page (phone friendly) and its small JSON routes. Same login as the app.
Tabs in one page: Download (any coin, any day), Backtest, Live scanner, Settings (all pump numbers live here)."""
import calendar, json, time
from urllib.parse import urlparse, parse_qs
import pump_config as cfg, pump_download as D, pump_live, pump_validate as V

PAGE = """<!doctype html><html lang="hi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#0b0f17"><title>Pump system</title><style>
:root{--bg:#0b0f17;--card:#131a27;--card2:#192233;--line:#26324a;--tx:#eaf1ff;--dim:#8d9bb8;--ac:#22d3a6;--ac2:#3b82f6;--dn:#ff5a6b;--r:14px}
*{box-sizing:border-box;overscroll-behavior-y:none;-webkit-tap-highlight-color:transparent}
body{margin:0;background:var(--bg);color:var(--tx);font:15px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;padding-bottom:40px}
header{position:sticky;top:0;z-index:5;background:rgba(11,15,23,.94);backdrop-filter:blur(8px);border-bottom:1px solid var(--line);padding:10px 14px 0}
.top{display:flex;align-items:center;justify-content:space-between;gap:8px}.top a{color:var(--dim);text-decoration:none;font-size:14px}
h1{margin:0;font-size:18px;letter-spacing:.2px}.pill{font-size:12px;padding:3px 10px;border-radius:99px;background:#2a3350;color:var(--dim)}.pill.on{background:#0d3b30;color:var(--ac)}
nav{display:flex;gap:4px;margin-top:8px;overflow-x:auto}nav button{flex:1;background:none;border:0;color:var(--dim);padding:10px 6px;font-size:14px;border-bottom:3px solid transparent;border-radius:0;margin:0;white-space:nowrap}
nav button.on{color:var(--ac);border-bottom-color:var(--ac);font-weight:600}
main{padding:14px;max-width:720px;margin:0 auto}section{display:none}section.on{display:block}
.card{background:var(--card);border:1px solid var(--line);border-radius:var(--r);padding:14px;margin-bottom:12px}
h2{margin:0 0 4px;font-size:16px}h3{margin:14px 0 6px;font-size:13px;color:var(--ac);text-transform:uppercase;letter-spacing:.6px}.d{color:var(--dim);font-size:13px}
label{display:block;margin:12px 0 4px;font-size:13px;color:var(--dim)}
input,select{width:100%;background:var(--card2);color:var(--tx);border:1px solid var(--line);border-radius:10px;padding:12px;font-size:16px;outline:none}
input:focus,select:focus{border-color:var(--ac)}input[type=checkbox]{width:22px;height:22px;vertical-align:middle;margin-right:8px;accent-color:var(--ac)}
.up{text-transform:uppercase;letter-spacing:1px;font-weight:600}
.two{display:grid;grid-template-columns:1fr 1fr;gap:10px}
button{background:var(--ac);color:#04231b;border:0;border-radius:11px;padding:12px 16px;font-size:15px;font-weight:600;margin:4px 6px 4px 0}
button.g{background:var(--card2);color:var(--tx);border:1px solid var(--line)}button.r{background:var(--dn);color:#fff}button.b{background:var(--ac2);color:#fff}
button.x{background:none;color:var(--dn);padding:8px 10px;margin:0;font-size:18px}button.big{width:100%;padding:14px;margin:12px 0 0}
.row2{display:grid;grid-template-columns:1.1fr 1.4fr auto;gap:8px;margin-top:8px;align-items:center}
.steps button{display:block;width:100%;text-align:left;margin:6px 0}.steps small{display:block;font-weight:400;opacity:.8}
pre{white-space:pre-wrap;word-break:break-word;font:12px/1.45 ui-monospace,Menlo,monospace;background:#0a0e16;border:1px solid var(--line);border-radius:10px;padding:10px;margin:8px 0 0;color:#cfe0ff;max-height:46vh;overflow:auto}
.stat{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin:10px 0}.stat div{background:var(--card2);border-radius:10px;padding:8px;text-align:center}.stat b{display:block;font-size:18px}.stat span{font-size:11px;color:var(--dim)}
.sw{display:flex;gap:8px}.sw button{flex:1;margin:0;padding:14px}.msg{margin-top:8px;font-size:13px;min-height:18px}.ok{color:var(--ac)}.bad{color:var(--dn)}
.prm{display:flex;justify-content:space-between;align-items:center;gap:10px;padding:8px 0;border-bottom:1px solid var(--line)}.prm div{flex:1}.prm small{display:block;color:var(--dim);font-size:12px}.prm input{width:120px;text-align:right}.prm input[type=checkbox]{width:24px}
</style></head><body>
<header><div class="top"><a href="/app">&larr; App</a><h1>&#9889; Pump system</h1><span id="pill" class="pill">Live OFF</span></div>
<nav id="nav"><button data-t="dl">Download</button><button data-t="bt">Backtest</button><button data-t="lv">Live</button><button data-t="st">Settings</button></nav></header>
<main>

<section id="dl"><div class="card"><h2>Data Download</h2><div class="d">किसी भी coin का पंप वाला डेटा CSV में। नाम सिर्फ़ TAO लिखो, USDT अपने-आप लग जाएगा।</div>
<label>Coin का नाम</label><input id="sym" class="up" list="cl" oninput="up(this);coins(this.value)" placeholder="TAO" autocomplete="off" autocapitalize="characters" autocorrect="off" spellcheck="false">
<datalist id="cl"></datalist>
<label>पंप वाली तारीख (UTC)</label><input id="day" type="date">
<div class="two"><div><label>कितने दिन पहले से</label><input id="bef" type="number" value="5" min="0" inputmode="numeric"></div><div><label>कितने दिन बाद तक</label><input id="aft" type="number" value="2" min="0" inputmode="numeric"></div></div>
<label>Candle size</label><select id="iv"><option>1m</option><option>3m</option><option selected>5m</option><option>15m</option><option>30m</option><option>1h</option><option>4h</option><option>1d</option></select>
<label><input type="checkbox" id="oi" checked>Open Interest <span class="d">(सिर्फ़ पिछले 30 दिन का मिलता है)</span></label>
<label><input type="checkbox" id="fr" checked>Funding rate</label>
<button class="big" onclick="dl()">&#11015; CSV Download</button><div id="dls" class="msg"></div></div></section>

<section id="bt"><div class="card"><h2>Backtest</h2><div class="d">कोड हर कैंडल पर सिर्फ़ उस समय तक का डेटा देखता है, आगे का कुछ नहीं। हर लाइन में एक coin और उसकी पंप वाली तारीख।</div>
<h3>Group A &middot; टेस्ट वाले coins</h3><div id="ra"></div><button class="g" onclick="addRow('a')">+ coin जोड़ो</button><button onclick="saveG('a')">Save A</button>
<h3>Group B &middot; बाद वाले नए coins (जाँच के लिए)</h3><div id="rb"></div><button class="g" onclick="addRow('b')">+ coin जोड़ो</button><button onclick="saveG('b')">Save B</button>
<div id="gm" class="msg"></div></div>
<div class="card steps"><h2>चलाओ</h2>
<button class="b" onclick="run('a')">1 &middot; Group A टेस्ट<small>हर सेंसर और combined: पंप पकड़ा या नहीं, कितना पहले, कितने झूठे अलर्ट</small></button>
<button class="b" onclick="run('sweep')">2 &middot; Settings sweep<small>कौन सी सेटिंग उस पंप को पहले पकड़ पाती (Live OFF होना चाहिए)</small></button>
<button class="b" onclick="run('b')">3 &middot; Group B जाँच<small>वही सेटिंग नए coins पर: overfitting चेक</small></button>
<button class="g" onclick="run('find')">Pumped coins खुद खोजो</button><button class="g" onclick="run('clean')">Raw data हटाओ</button>
<div id="st" class="msg d"></div><pre id="log"></pre></div>
<div class="card"><h2>नतीजा</h2><button class="g" onclick="res('a')">Group A</button><button class="g" onclick="res('s')">Sweep</button><button class="g" onclick="res('b')">Group B</button><pre id="res">ऊपर से कोई नतीजा चुनो</pre></div></section>

<section id="lv"><div class="card"><h2>Live scanner</h2><div class="d">हर 5 मिनट में सारे CoinDCX coins। अलर्ट Telegram पर जाता है।</div>
<div class="sw"><button onclick="live(1)">ON</button><button class="r" onclick="live(0)">OFF</button></div>
<div class="stat"><div><b id="s1">-</b><span>cycles</span></div><div><b id="s2">-</b><span>coins</span></div><div><b id="s3">-</b><span>caught</span></div></div>
<div id="lv1" class="d"></div></div>
<div class="card"><h2>Journal (forward test)</h2><div class="d">हर अलर्ट का कारण, और बाद में सही/गलत + गलती की वजह।</div><pre id="jr">अभी कोई अलर्ट नहीं</pre></div>
<div class="card"><h3>Alerts</h3><pre id="rc">अभी कोई नहीं</pre><h3>Watch list (जिन coins में सेंसर दिखा)</h3><pre id="wl">खाली</pre><div id="cu" class="d" style="margin-top:8px"></div></div></section>

<section id="st2"><div class="card"><h2>Settings</h2><div class="d">सारे पंप नंबर यहीं बदलते हैं, फ़ाइल में कुछ नहीं।</div><div id="set"></div>
<button class="big" onclick="saveSet()">Save</button><button class="g big" onclick="resetSet()">Default पर लौटाओ</button><div id="sm" class="msg"></div></div></section>
</main>
<script>
const $=i=>document.getElementById(i);
const HINT={pct:'पंप = कितना % उछाल',window:'कितनी candles में (5m x)',hit_pct:'alert सही = इतना % ऊपर गया',horizon:'कितनी candles तक देखो',cooldown:'alert के बाद इतनी candles चुप',lookback:'strategy को कितनी पुरानी candles दिखें',volume_multiplier:'volume औसत का कितना गुना',base_candles:'औसत कितनी candles का',min_buy_ratio:'खरीदार कम से कम (0 = बंद)',min_return_pct:'कम से कम % बढ़त',bars:'कितनी candles',breakout_candles:'कितनी पुरानी high तोड़े',oi_change_percent:'OI कितना % बढ़े',min_price_pct:'साथ में price कम से कम %',negative_below:'funding इससे नीचे',positive_above:'funding इससे ऊपर',MIN_STRATEGIES:'कम से कम कितने सेंसर एक साथ',min_quote_vol_24h:'24h volume कम से कम ($)',cooldown_min:'एक coin का अगला alert (मिनट)',enabled:'चालू',days:'पिछले कितने दिन में खोजो',min_day_gain:'दिन में कम से कम % उछाल',group_a:'Group A कितने coins',group_b:'Group B कितने coins',before_days:'पंप से पहले के दिन',after_days:'पंप के बाद के दिन',workers:'एक साथ requests',klines:'live: कितनी candles',delay_s:'candle बंद होने के बाद सेकंड',max_run_pct:'पहले ही इतना % चढ़ चुका तो अलर्ट नहीं (देर से)',run_candles:'यह % कितनी पिछली candles की सबसे नीची कीमत से',min_candle_usd:'पतला coin हटाओ: हर 5m candle में कम से कम $',confirm_candles:'सेंसर लगातार इतनी candles सहमत हों (1 = बंद)',max_wick_ratio:'candle ऊपर से इतना लौटी तो स्पाइक मानो (1 = बंद)',multiplier:'औसत का कितना गुना',candles:'कितनी candles',max_price_pct:'इस दौरान कीमत इससे ज़्यादा न बढ़ी हो'};
async function j(u){const r=await fetch(u);if(r.status==401){location.href='/app';return null}return r.json()}
function up(e){const v=e.value.toUpperCase().replace(/[^A-Z0-9]/g,'');if(v!==e.value)e.value=v}
function tab(t){document.querySelectorAll('section').forEach(s=>s.classList.toggle('on',s.id===(t==='st'?'st2':t)));document.querySelectorAll('#nav button').forEach(b=>b.classList.toggle('on',b.dataset.t===t));try{localStorage.setItem('pump_tab',t)}catch(e){}}
document.querySelectorAll('#nav button').forEach(b=>b.onclick=()=>tab(b.dataset.t));
async function coins(q){if(q.length<2)return;const d=await j('/pump/coins?q='+encodeURIComponent(q));if(d)$('cl').innerHTML=d.coins.map(c=>'<option value="'+c.replace('USDT','')+'">').join('')}
async function dl(){const s=$('sym').value.trim().toUpperCase(),d=$('day').value;if(!s||!d){$('dls').className='msg bad';$('dls').textContent='coin और तारीख दोनों भरो';return}
$('dls').className='msg d';$('dls').textContent='डाउनलोड हो रहा है... (कुछ सेकंड से 1 मिनट)';
const u='/pump/download?sym='+s+'&day='+d+'&before='+$('bef').value+'&after='+$('aft').value+'&iv='+$('iv').value+'&oi='+($('oi').checked?1:0)+'&fr='+($('fr').checked?1:0);
try{const r=await fetch(u);if(r.status==401){location.href='/app';return}if(!r.ok){$('dls').className='msg bad';$('dls').textContent='❌ '+(await r.json()).error;return}
const b=await r.blob(),a=document.createElement('a');a.href=URL.createObjectURL(b);a.download=s+'_'+d+'_'+$('iv').value+'.csv';document.body.appendChild(a);a.click();a.remove();$('dls').className='msg ok';$('dls').textContent='✅ फ़ाइल डाउनलोड हो गई ('+Math.round(b.size/1024)+' KB)'}catch(e){$('dls').className='msg bad';$('dls').textContent='❌ '+e}}
const GR={a:[],b:[]};
function render(g){$('r'+g).innerHTML=GR[g].map((r,i)=>'<div class="row2"><input class="up" placeholder="COIN" value="'+r.c+'" autocapitalize="characters" autocomplete="off" autocorrect="off" spellcheck="false" oninput="up(this);GR.'+g+'['+i+'].c=this.value"><input type="date" value="'+r.d+'" onchange="GR.'+g+'['+i+'].d=this.value"><button class="x" onclick="delRow(\\''+g+'\\','+i+')">✕</button></div>').join('')}
function addRow(g){GR[g].push({c:'',d:''});render(g)}
function delRow(g,i){GR[g].splice(i,1);render(g)}
async function loadG(){for(const g of['a','b']){const d=await j('/pump/group?g='+g);if(!d)continue;GR[g]=d.text.split('\\n').filter(x=>x.trim()).map(l=>{const p=l.trim().split(/\\s+/);return{c:(p[0]||'').replace(/USDT$/,''),d:p[1]||''}});if(!GR[g].length)GR[g]=[{c:'',d:''}];render(g)}}
async function saveG(g){const rows=GR[g].filter(r=>r.c||r.d);if(rows.some(r=>!r.c||!r.d)){$('gm').className='msg bad';$('gm').textContent='❌ हर लाइन में coin और तारीख दोनों भरो';return}
const d=await j('/pump/group/save?g='+g+'&text='+encodeURIComponent(rows.map(r=>r.c+' '+r.d).join('\\n')));if(d){$('gm').className='msg '+(d.errors.length?'bad':'ok');$('gm').textContent=d.errors.length?'❌ '+d.errors.join(' | '):'✅ Group '+g.toUpperCase()+' save हो गया ('+rows.length+' coins)'}}
async function run(a){const d=await j('/pump/run?action='+a);if(d&&!d.ok)alert(d.error);tick()}
async function res(g){const d=await j('/pump/result?g='+g);if(d)$('res').textContent=d.text}
async function live(v){await j('/pump/live?on='+v);tick()}
async function tick(){const d=await j('/pump/status');if(!d)return;const s=d.validate,l=d.live;
$('st').textContent=(s.running?'⏳ चल रहा है: '+s.running:'खाली')+' | groups: '+(s.groups?'हाँ':'नहीं');
$('log').textContent=(s.log||[]).join('\\n')+(s.last?'\\n\\n'+s.last:'');
$('pill').textContent='Live '+(l.on?'ON':'OFF');$('pill').className='pill'+(l.on?' on':'');
$('s1').textContent=l.cycles;$('s2').textContent=l.coins;$('s3').textContent=l.caught;
$('lv1').textContent='last cycle '+(l.last_cycle_s??'-')+'s'+(l.last_error?' | error: '+l.last_error:'');
$('wl').textContent=(l.watch||[]).map(w=>w.sym+'  '+w.since_min+' min  '+w.sensors.join('+')+(w.alerted?'  ALERTED':'')).join('\\n')||'खाली';
$('cu').textContent=(l.custom&&l.custom.length?'मेरे setups: '+l.custom.join(', '):'मेरे setups: कोई नहीं')+(l.custom_error?' | ❌ '+l.custom_error:'');
$('jr').textContent=(l.journal||[]).map(r=>new Date(r.ts).toLocaleString()+'  '+r.sym+'  @'+r.price+'\\n  कारण: '+Object.entries(r.reasons).map(e=>e[0]+' ('+e[1]+')').join('; ')+'\\n  '+(r.verdict?r.why:'⏳ चल रहा'+(r.path?': अब तक ऊपर +'+r.path.peak+'%, नीचे '+r.path.trough+'%':''))).join('\\n\\n')||'अभी कोई अलर्ट नहीं';
$('rc').textContent=(l.recent||[]).map(a=>new Date(a.ts).toLocaleTimeString()+' '+a.sym+' '+a.score+'/100 @'+a.price).join('\\n')||'अभी कोई नहीं'}
function walk(o,p){let h='';for(const[k,v]of Object.entries(o)){const path=p.concat(k).join('.');
if(v!==null&&typeof v==='object'){h+='<h3>'+k+'</h3>'+walk(v,p.concat(k))}
else{h+='<div class="prm"><div>'+k+'<small>'+(HINT[k]||'')+'</small></div>'+(typeof v==='boolean'?'<input type="checkbox" data-p="'+path+'" '+(v?'checked':'')+'>':'<input type="number" step="any" inputmode="decimal" data-p="'+path+'" value="'+v+'">')+'</div>'}}return h}
async function loadSet(){const d=await j('/pump/settings');if(d)$('set').innerHTML=walk(d.cfg,[])}
async function saveSet(){const o={};document.querySelectorAll('#set input').forEach(i=>{const p=i.dataset.p.split('.');let t=o;for(let n=0;n<p.length-1;n++)t=t[p[n]]=t[p[n]]||{};t[p[p.length-1]]=i.type==='checkbox'?i.checked:i.value});
const d=await j('/pump/settings/save?json='+encodeURIComponent(JSON.stringify(o)));if(d){$('sm').className='msg '+(d.errors.length?'bad':'ok');$('sm').textContent=d.errors.length?'❌ '+d.errors.join(' | '):'✅ Save हो गया'}loadSet()}
async function resetSet(){await j('/pump/settings/reset');$('sm').className='msg ok';$('sm').textContent='Default लौटा दिए';loadSet()}
$('day').value=new Date(Date.now()-864e5).toISOString().slice(0,10);
let t0='dl';try{t0=localStorage.getItem('pump_tab')||'dl'}catch(e){}tab(['dl','bt','lv','st'].includes(t0)?t0:'dl');
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
    sym = sym if sym.endswith("USDT") or not sym else sym + "USDT"  # you may type just TAO
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
            return js(V.start(a) if a in ("find", "a", "b", "clean", "sweep") else {"ok": False, "error": "unknown action"})
        if u.path == "/pump/result":
            g = (q.get("g") or ["a"])[0]
            return js({"text": V.saved_text(g if g in ("a", "b", "s") else "a") + ("\n\n" + V.compare() if g == "b" else "")})
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
