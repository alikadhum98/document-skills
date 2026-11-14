"""Live Ear (PC): the browser's own speech recognition, kept alive while minimized.

Run:  python ear_local.py
It starts a tiny local server on http://127.0.0.1:8765 and opens it in Edge
as a small app window. Press the start button once. Every settled sentence is
appended to COP31_live.txt in Google Drive, and a heartbeat goes to
COP31_live_status.txt every 20 seconds. Standard library only: nothing to
install beyond Python itself.
"""
import datetime, json, os, shutil, subprocess, sys, threading, time, webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = 8765
VERSION = "web-2026-11-14f"


def find_drive():
    for d in "GHIJKLMNOPEFD":
        p = d + ":\\My Drive"
        if os.path.isdir(p):
            return p
    p = os.path.join(os.path.expanduser("~"), "Desktop")
    return p if os.path.isdir(p) else os.path.expanduser("~")


DRIVE = find_drive()
if sys.stdout is None:  # started with pythonw: no console window
    _log = open(os.path.join(os.path.expanduser("~"), "LiveEar_PC.log"), "a", encoding="utf-8")
    sys.stdout = sys.stderr = _log
OUT = os.path.join(DRIVE, "COP31_live.txt")
STATUS = os.path.join(DRIVE, "COP31_live_status.txt")
LOCK = threading.Lock()
TOKEN = "%x" % int(time.time() * 1000)  # pages served by an older copy carry no or another token
PENDING = []
SESS_DIR = os.path.join(os.path.expanduser("~"), "LiveEar_Sessions")
CURRENT = {"path": None}
PAGE_URL = "https://claude.ai/artifact/9ag5mqwy8LRaGpwUmwi3za"


def safe_name(name):
    keep = "".join(c if (c.isalnum() or c in " -_.") else " " for c in name).strip()
    return " ".join(keep.split())[:60] or "session"


def new_session(name):
    os.makedirs(SESS_DIR, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y-%m-%d_%H%M")
    CURRENT["path"] = os.path.join(SESS_DIR, f"{stamp}_{safe_name(name)}.txt")


def to_session(line):
    if not CURRENT["path"]:
        return
    try:
        with open(CURRENT["path"], "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def list_sessions():
    out = []
    if not os.path.isdir(SESS_DIR):
        return out
    for fn in sorted(os.listdir(SESS_DIR), reverse=True)[:100]:
        if not fn.endswith(".txt"):
            continue
        full = os.path.join(SESS_DIR, fn)
        try:
            with open(full, encoding="utf-8") as f:
                rows = [r for r in f.read().splitlines() if r.strip()]
        except OSError:
            rows = []
        body = [r for r in rows if "=====" not in r]
        parts = fn[:-4].split("_", 2)
        out.append({"file": fn, "date": parts[0] if parts else "", "time": (parts[1][:2] + ":" + parts[1][2:]) if len(parts) > 1 else "",
                    "name": parts[2] if len(parts) > 2 else fn, "lines": len(body),
                    "last": body[-1][1:9] if body and body[-1].startswith("[") else ""})
    return out


# ---------- keep the PC awake while listening ----------
AWAKE = {"on": False}


def awake_loop():
    while True:
        if AWAKE["on"] and os.name == "nt":
            try:
                import ctypes
                ctypes.windll.kernel32.SetThreadExecutionState(0x00000001)  # ES_SYSTEM_REQUIRED
            except Exception:
                pass
        time.sleep(30)


# ---------- automatic fallback to the offline Whisper ear ----------
PAGE_STATE = {"ok": True, "seen": 0.0, "bad_since": 0.0, "good_since": 0.0}
FALLBACK = {"proc": None}


def find_whisper_ear():
    here = os.path.dirname(os.path.abspath(__file__))
    for p in (os.path.join(here, "live_ear.py"), os.path.join(os.path.expanduser("~"), "LiveEar", "live_ear.py")):
        if os.path.isfile(p):
            return p
    return None


def python_exe():
    exe = sys.executable or "python"
    if exe.lower().endswith("pythonw.exe"):
        alt = exe[:-len("pythonw.exe")] + "python.exe"
        if os.path.isfile(alt):
            return alt
    return exe


def start_fallback(why):
    if FALLBACK["proc"] and FALLBACK["proc"].poll() is None:
        return
    script = find_whisper_ear()
    now = datetime.datetime.now().strftime("%H:%M:%S")
    if not script:
        append(f"[{now}] ===== FALLBACK unavailable: live_ear.py not found =====")
        PAGE_STATE["bad_since"] = time.time() + 600  # do not retry for ten minutes
        return
    append(f"[{now}] ===== FALLBACK START ({why}) small.en =====")
    flags = 0x08000000 if os.name == "nt" else 0  # CREATE_NO_WINDOW
    try:
        FALLBACK["proc"] = subprocess.Popen([python_exe(), script, "--model", "small.en", "--drive", DRIVE],
                                            creationflags=flags, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError as e:
        append(f"[{now}] ===== FALLBACK failed: {e} =====")


def stop_fallback(why):
    p = FALLBACK["proc"]
    if p and p.poll() is None:
        try:
            p.terminate()
        except OSError:
            pass
        append(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] ===== FALLBACK END ({why}) =====")
    FALLBACK["proc"] = None


def fallback_loop():
    while True:
        time.sleep(5)
        now = time.time()
        active = CURRENT["path"] is not None
        if not active:
            stop_fallback("session stopped")
            continue
        stale = now - PAGE_STATE["seen"] > 150  # minimized windows send their heartbeat late
        bad = stale or not PAGE_STATE["ok"]
        if bad:
            PAGE_STATE["good_since"] = 0.0
            if not PAGE_STATE["bad_since"]:
                PAGE_STATE["bad_since"] = now
            if now - PAGE_STATE["bad_since"] > 60:
                start_fallback("browser silent" if stale else "browser failing")
        else:
            PAGE_STATE["bad_since"] = 0.0
            if not PAGE_STATE["good_since"]:
                PAGE_STATE["good_since"] = now
            if FALLBACK["proc"] and now - PAGE_STATE["good_since"] > 30:
                stop_fallback("browser back")
        p = FALLBACK["proc"]
        if p and p.poll() is not None:
            append(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] ===== FALLBACK exited (code {p.returncode}) =====")
            FALLBACK["proc"] = None
            PAGE_STATE["bad_since"] = now + 600


def append(line):
    print(line, flush=True)
    to_session(line)
    with LOCK:
        PENDING.append(line)
        for _ in range(3):
            try:
                with open(OUT, "a", encoding="utf-8") as f:
                    f.write("\n".join(PENDING) + "\n")
                PENDING.clear()
                return
            except OSError:
                time.sleep(0.4)


def status(state):
    try:
        with open(STATUS, "w", encoding="utf-8") as f:
            f.write(f"{state} {datetime.datetime.now().isoformat(timespec='seconds')}\n")
    except OSError:
        pass


PAGE = r"""<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Live Ear PC</title>
<style>
:root{--bg:#f3f5f6;--panel:#fff;--fg:#14211f;--muted:#5d6b69;--line:#d9e0e0;--accent:#0b6e78;--rec:#c62f2f;--warn:#a15c00}
@media (prefers-color-scheme:dark){:root{--bg:#0f1716;--panel:#162220;--fg:#e4ecea;--muted:#93a4a1;--line:#29393a;--accent:#3fb3be;--rec:#ff6b6b;--warn:#f0b450;color-scheme:dark}}
body{margin:0;background:var(--bg);color:var(--fg);font:15px "Segoe UI",Tahoma,sans-serif}
.app{display:flex;flex-direction:column;gap:10px;padding:14px 16px}
h1{margin:0;font-size:1.25rem}
.row{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
select,button{font:inherit;border-radius:8px;border:1px solid var(--line);background:var(--panel);color:var(--fg);padding:9px 12px}
.mic{background:var(--accent);color:#fff;border:none;font-weight:700;padding:14px;font-size:1.1rem}
.mic.on{background:var(--rec)}
.st{font-size:.9rem;color:var(--muted)}
.st b{color:var(--fg)}
.warn{color:var(--warn);font-weight:600}
.tx{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:8px 12px;height:55vh;overflow-y:auto;direction:ltr;text-align:left;font-family:"Segoe UI",Arial,sans-serif;line-height:1.5}
.tx div{padding:4px 0;border-bottom:1px solid var(--line)}
.tx time{color:var(--muted);font:12px Consolas,monospace;margin-right:8px}
.tx .p{color:var(--muted);font-style:italic;border:none}
.acts{display:grid;grid-template-columns:repeat(4,1fr);gap:8px}
@media (max-width:420px){.acts{grid-template-columns:1fr 1fr}}
.acts button{font-weight:700;padding:12px 6px}
.acts .pri{background:var(--accent);color:#fff;border:none}
.hist{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:6px 10px;max-height:40vh;overflow-y:auto}
.hrow{display:flex;justify-content:space-between;gap:8px;align-items:center;padding:8px 2px;border-bottom:1px solid var(--line);cursor:pointer}
.hrow:last-child{border-bottom:none}
.hrow b{min-width:0;overflow-wrap:anywhere}
.hrow span{color:var(--muted);font-size:.85rem;white-space:nowrap}
.back{margin-bottom:6px}
</style></head><body><div class="app">
<h1>الأذن الحية على الحاسوب</h1>
<div class="row">
 <label>اسم الجلسة <input id="sname" placeholder="مثلا Article 6.2 informals" style="font:inherit;border-radius:8px;border:1px solid var(--line);background:var(--panel);color:var(--fg);padding:9px 10px;min-width:0;width:15em;max-width:100%"></label>
 <label>لغة القاعة <select id="lang"><option value="en-US">English</option><option value="en-GB">English UK</option><option value="ar-IQ">العربية</option></select></label>
</div>
<button class="mic" id="mic">ابدأ السماع</button>
<div class="st">الحالة: <b id="state">متوقفة</b> | الأسطر: <b id="n">0</b> | آخر كلام: <b id="last">لا يوجد</b></div>
<div class="st warn" id="warn" hidden></div>
<div class="st">يمكنك تصغير هذه النافذة بعد البدء. النص يكتب في COP31_live.txt على Drive.</div>
<div class="acts">
 <button id="reply" class="pri" type="button">رد</button>
 <button id="sum" type="button">ملخص</button>
 <button id="histBtn" type="button">السجل</button>
 <button id="folder" type="button">مجلد الجلسات</button>
</div>
<div class="st" id="hint">زر (رد) و(ملخص) يفتحان صفحة الصياغة في المتصفح وتبدأ وحدها. النص يصلها عبر Drive، فانتظر ثوان بعد آخر جملة.</div>
<div class="hist" id="hist" hidden><div id="hlist"></div></div>
<div class="tx" id="tx"></div>
<div class="row"><button id="quit" type="button">أغلق البرنامج</button></div>
</div>
<script>
const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
const $=id=>document.getElementById(id);
let rec=null, want=false, n=0, partialEl=null, ctx=null, wake=null;
let phraseStart=null, emitted=0;               // words of the current phrase already written
let lastResultAt=0, lastStartAt=0, lastRestartAt=0, reasons=[], failingSince=0;
const EMIT_AFTER_MS=12000, STALL_MS=20000, GAP_LOG_MS=20000;
try{$("lang").value=localStorage.getItem("lang")||"en-US"}catch(e){}
$("lang").onchange=()=>{try{localStorage.setItem("lang",$("lang").value)}catch(e){} if(want) forceRestart("lang");};
const pad=x=>String(x).padStart(2,"0");
const hms=d=>pad(d.getHours())+":"+pad(d.getMinutes())+":"+pad(d.getSeconds());
const TOKEN="__TOKEN__";
let staleShown=false;
function post(path,obj){return fetch(path,{method:"POST",headers:{"Content-Type":"application/json","X-Ear-Token":TOKEN},body:JSON.stringify(obj)})
  .then(r=>{ if(r.status===409 && !staleShown){ staleShown=true; want=false; try{rec&&rec.stop()}catch(e){} document.body.innerHTML="<p style='padding:20px'>هذه نافذة قديمة للبرنامج. أغلقها، فالنسخة الجديدة تعمل في نافذة أخرى.</p>"; } return r; })
  .catch(()=>{})}
function beep(){try{ctx=ctx||new AudioContext();[0,.35].forEach(o=>{const s=ctx.createOscillator(),g=ctx.createGain();s.frequency.value=880;g.gain.value=.15;s.connect(g);g.connect(ctx.destination);s.start(ctx.currentTime+o);s.stop(ctx.currentTime+o+.18)})}catch(e){}}
function warn(t){$("warn").textContent=t;$("warn").hidden=!t}
async function keepAwake(){ try{ if(want && !wake && navigator.wakeLock && document.visibilityState==="visible"){ wake=await navigator.wakeLock.request("screen"); wake.addEventListener("release",()=>{wake=null}); } }catch(e){ wake=null; } }
document.addEventListener("visibilitychange", keepAwake);
function show(time,text,partial){
  if(partial){ if(!partialEl){partialEl=document.createElement("div");partialEl.className="p";$("tx").appendChild(partialEl)} partialEl.textContent=text; }
  else{ if(partialEl){partialEl.remove();partialEl=null}
    const d=document.createElement("div"); const t=document.createElement("time"); t.textContent=time; d.append(t,document.createTextNode(text)); $("tx").appendChild(d);
    while($("tx").children.length>300) $("tx").firstChild.remove(); }
  $("tx").scrollTop=$("tx").scrollHeight;
}
function setUi(){ $("mic").textContent=want?"أوقف السماع":"ابدأ السماع"; $("mic").classList.toggle("on",want); }
function alive(){
  const now=Date.now();
  if(lastResultAt && now-lastResultAt>GAP_LOG_MS){
    const secs=Math.round((now-lastResultAt)/1000);
    const why=[...new Set(reasons)].join(" ")||"silence";
    post("/gap",{time:hms(new Date(lastResultAt)),secs,why});
  }
  reasons=[]; lastResultAt=now; failingSince=0;
}
function writeLine(time,text){
  alive();
  n++; $("n").textContent=n; $("last").textContent=time; show(time,text,false); post("/line",{time,text});
}
function build(){
  if(rec){ try{ rec.onend=null; rec.onerror=null; rec.onresult=null; rec.abort(); }catch(e){} }
  rec=new SR(); rec.continuous=true; rec.interimResults=true; rec.lang=$("lang").value; rec.maxAlternatives=1;
  rec.onstart=()=>{ lastStartAt=Date.now(); $("state").textContent="تسمع الآن"; warn(""); };
  rec.onresult=e=>{
    let interim="";
    for(let i=e.resultIndex;i<e.results.length;i++){
      const r=e.results[i], text=r[0].transcript.trim();
      if(!text) continue;
      if(r.isFinal){
        const words=text.split(/\s+/), rest=words.slice(emitted).join(" ");
        const time=hms(phraseStart||new Date());
        phraseStart=null; emitted=0;
        if(rest) writeLine(time,rest); else alive();
      } else interim+=text+" ";
    }
    if(interim){
      if(!phraseStart) phraseStart=new Date();
      alive(); // words are arriving: recognition is alive
      const words=interim.trim().split(/\s+/);
      show("",words.slice(emitted).join(" "),true);
      // long unbroken speech: write the settled part now, without stopping recognition
      if(Date.now()-phraseStart.getTime()>EMIT_AFTER_MS && words.length-3>emitted){
        const chunk=words.slice(emitted, words.length-3).join(" ");
        const time=hms(phraseStart); emitted=words.length-3; phraseStart=new Date();
        writeLine(time,chunk);
      }
    }
  };
  rec.onerror=e=>{ reasons.push(e.error);
    if(e.error==="not-allowed"||e.error==="service-not-allowed"){ want=false; setUi(); warn("الميكروفون ممنوع. اسمح به من أيقونة القفل بجانب العنوان ثم ابدأ من جديد."); beep(); post("/status",{state:"blocked",ok:false}); }
    else if(e.error==="network"){ warn("انقطع الإنترنت، يعاد الاتصال تلقائيا."); }
    else if(e.error==="audio-capture"){ warn("لا يصل صوت من الميكروفون. تأكد من اختيار الميكروفون الصحيح."); }
  };
  rec.onend=()=>{
    if(!want){ $("state").textContent="متوقفة"; post("/status",{state:"stopped",ok:true}); return; }
    $("state").textContent="يعاد التشغيل";
    emitted=0; phraseStart=null;
    // restart at once: timers are slowed down while the window is minimized
    try{ rec.lang=$("lang").value; rec.start(); }catch(err){ forceRestart("start-failed"); }
  };
}
function forceRestart(why){
  if(!want) return;
  reasons.push(why); lastRestartAt=Date.now();
  build();
  try{ rec.start(); }catch(e){ reasons.push("start-failed"); }
}
// watchdog: recognition alive but silent for too long, or never restarted
setInterval(()=>{
  if(!want) return;
  const now=Date.now();
  if(now-Math.max(lastResultAt,lastStartAt,lastRestartAt)>STALL_MS) forceRestart("stall");
  const hard = reasons.some(r=>r!=="no-speech" && r!=="aborted" && r!=="stall" && r!=="lang");
  const silentLong = now-lastResultAt>60000;
  if(silentLong && (hard || now-lastStartAt>60000)){ if(!failingSince) failingSince=now; } else failingSince=0;
  if(failingSince && now-failingSince>5000) warn("السماع متعثر منذ أكثر من دقيقة، والبرنامج يشغل التسجيل الاحتياطي.");
},3000);
function stopListening(){ if(!want) return; want=false; setUi(); try{rec&&rec.stop()}catch(e){} post("/stop",{}); }
function startListening(){
  if(!SR || want) return;
  try{ctx=ctx||new AudioContext();ctx.resume()}catch(e){}
  want=true; setUi(); keepAwake();
  post("/start",{lang:$("lang").value, name:$("sname").value.trim()});
  $("tx").replaceChildren(); n=0; $("n").textContent="0";
  lastResultAt=Date.now(); reasons=[]; failingSince=0; emitted=0; phraseStart=null;
  build(); try{ rec.start(); }catch(e){}
}
$("mic").onclick=()=>{
  if(!SR){ warn("هذا المتصفح لا يدعم التعرف على الكلام. افتح الصفحة في Edge أو Chrome."); return; }
  if(want) stopListening(); else startListening();
};
// remote commands placed in Drive by Claude, relayed by the local server
setInterval(async()=>{
  try{
    const c=await (await fetch("/cmd")).json();
    if(c.cmd==="start"){ if(c.name) $("sname").value=c.name; startListening(); }
    else if(c.cmd==="stop") stopListening();
    else if(c.cmd==="quit"){ want=false; try{rec&&rec.stop()}catch(e){} document.body.innerHTML="<p style='padding:20px'>أغلق البرنامج بأمر من Claude. يمكنك إغلاق هذه النافذة.</p>"; }
  }catch(e){}
},3000);
$("reply").onclick=()=>post("/open",{what:"reply"});
$("sum").onclick=()=>post("/open",{what:"summary"});
$("folder").onclick=()=>post("/folder",{});
async function loadHist(){
  const box=$("hlist"); box.replaceChildren();
  let list=[]; try{ list=await (await fetch("/sessions")).json(); }catch(e){}
  if(!list.length){ box.textContent="لا توجد جلسات محفوظة بعد."; return; }
  list.forEach(x=>{ const r=document.createElement("div"); r.className="hrow";
    const b=document.createElement("b"); b.textContent=x.name;
    const sp=document.createElement("span"); sp.textContent=x.date+"  "+x.time+(x.last?" إلى "+x.last.slice(0,5):"")+"  "+x.lines+" سطر";
    r.append(b,sp); r.onclick=()=>showSession(x); box.appendChild(r); });
}
async function showSession(x){
  const box=$("hlist"); box.replaceChildren();
  const back=document.createElement("button"); back.className="back"; back.textContent="رجوع إلى القائمة"; back.onclick=loadHist;
  const pre=document.createElement("pre"); pre.style.cssText="white-space:pre-wrap;direction:ltr;text-align:left;margin:0;font:14px 'Segoe UI',Arial,sans-serif;line-height:1.5";
  try{ pre.textContent=await (await fetch("/session?f="+encodeURIComponent(x.file))).text(); }catch(e){ pre.textContent=""; }
  box.append(back,pre);
}
$("histBtn").onclick=()=>{ const h=$("hist"); h.hidden=!h.hidden; $("histBtn").classList.toggle("pri",!h.hidden); if(!h.hidden) loadHist(); };
$("quit").onclick=()=>{ want=false; try{rec&&rec.stop()}catch(e){} post("/quit",{}).then(()=>{ document.body.innerHTML="<p style='padding:20px'>أغلق البرنامج. يمكنك إغلاق هذه النافذة.</p>"; }); };
setInterval(()=>{
  if(!want){ post("/status",{state:"stopped",ok:true}); return; }
  const failing = !!(failingSince && Date.now()-failingSince>0);
  post("/status",{state: failing?"failing":($("state").textContent==="تسمع الآن"?"listening":"restarting"), ok:!failing});
},10000);
if(!SR) warn("هذا المتصفح لا يدعم التعرف على الكلام. افتح الصفحة في Edge أو Chrome.");
</script></body></html>"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _ok(self, body=b"ok", ctype="text/plain"):
        self.send_response(200)
        self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        from urllib.parse import urlparse, parse_qs
        u = urlparse(self.path)
        if u.path == "/cmd":
            c = {"cmd": CMD["cmd"], "name": CMD["name"]}
            CMD.update(cmd=None, name="")
            self._ok(json.dumps(c, ensure_ascii=False).encode("utf-8"), "application/json")
        elif u.path == "/sessions":
            self._ok(json.dumps(list_sessions(), ensure_ascii=False).encode("utf-8"), "application/json")
        elif u.path == "/session":
            fn = os.path.basename(parse_qs(u.query).get("f", [""])[0])
            try:
                with open(os.path.join(SESS_DIR, fn), encoding="utf-8") as f:
                    body = f.read()
            except OSError:
                body = ""
            self._ok(body.encode("utf-8"))
        else:
            self._ok(PAGE.replace("__TOKEN__", TOKEN).encode("utf-8"), "text/html")

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        try:
            data = json.loads(self.rfile.read(n) or b"{}")
        except ValueError:
            data = {}
        now = datetime.datetime.now().strftime("%H:%M:%S")
        if self.headers.get("X-Ear-Token") != TOKEN:
            # a window left over from an older copy: ignore it and tell it to stand down
            self.send_response(409)
            self.end_headers()
            return
        if self.path == "/line":
            text = " ".join(str(data.get("text", "")).split())
            if text:
                append(f"[{data.get('time') or now}] {text}")
        elif self.path == "/gap":
            append(f"[{data.get('time') or now}] ===== GAP {int(data.get('secs') or 0)} ثانية, {str(data.get('why') or '')[:60]} =====")
        elif self.path == "/start":
            new_session(str(data.get("name") or "session"))
            AWAKE["on"] = True
            PAGE_STATE.update(ok=True, seen=time.time(), bad_since=0.0, good_since=0.0)
            append(f"[{now}] ===== START {datetime.date.today()} web lang={data.get('lang', '')} v={VERSION} =====")
            status("web-listening")
        elif self.path == "/stop":
            append(f"[{now}] ===== STOP =====")
            CURRENT["path"] = None
            AWAKE["on"] = False
            stop_fallback("stopped")
            status("web-stopped")
        elif self.path == "/status":
            PAGE_STATE["seen"] = time.time()
            PAGE_STATE["ok"] = data.get("ok", True) is not False
            state = str(data.get("state", "unknown"))[:20]
            if FALLBACK["proc"]:
                state += "+fallback"
            status("web-" + state)
        elif self.path == "/open":
            what = "reply" if data.get("what") == "reply" else "summary"
            webbrowser.open(PAGE_URL + "#" + what)
        elif self.path == "/folder":
            os.makedirs(SESS_DIR, exist_ok=True)
            try:
                os.startfile(SESS_DIR)
            except (AttributeError, OSError):
                pass
        elif self.path == "/quit":
            stop_fallback("quit")
            status("web-off")
            self._ok()
            threading.Thread(target=self.server.shutdown, daemon=True).start()
            return
        self._ok()


# ---------- remote control through Drive ----------
CMD = {"cmd": None, "name": ""}
CMD_FILES = {"start": "COP31_ear_START.txt", "stop": "COP31_ear_STOP.txt", "quit": "COP31_ear_QUIT.txt"}


def command_loop(server):
    while True:
        time.sleep(3)
        for cmd, fn in CMD_FILES.items():
            path = os.path.join(DRIVE, fn)
            if not os.path.exists(path):
                continue
            name = ""
            try:
                with open(path, encoding="utf-8") as f:
                    name = " ".join(f.read().split())[:80]
            except OSError:
                pass
            try:
                os.remove(path)
            except OSError:
                pass
            now = datetime.datetime.now().strftime("%H:%M:%S")
            append(f"[{now}] ===== COMMAND {cmd.upper()} {name} =====".replace("  ", " "))
            if cmd == "quit":
                CMD.update(cmd="quit", name="")
                time.sleep(4)  # let the window hear it
                stop_fallback("quit")
                if CURRENT["path"]:
                    append(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] ===== STOP =====")
                    CURRENT["path"] = None
                status("web-off")
                server.shutdown()
                return
            CMD.update(cmd=cmd, name=name)


# ---------- one-time setup on this PC ----------
def ps(script, timeout=60):
    return subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
                          capture_output=True, text=True, timeout=timeout, creationflags=0x08000000)


def pc_setup():
    if os.name != "nt":
        return
    now = lambda: datetime.datetime.now().strftime("%H:%M:%S")
    notes = []
    # 1. start with Windows
    try:
        startup = os.path.join(os.environ.get("APPDATA", ""), "Microsoft", "Windows", "Start Menu", "Programs", "Startup")
        exe = sys.executable or "pythonw"
        if exe.lower().endswith("python.exe"):
            alt = exe[:-len("python.exe")] + "pythonw.exe"
            if os.path.isfile(alt):
                exe = alt
        me = os.path.abspath(__file__)
        with open(os.path.join(startup, "LiveEarPC.bat"), "w", encoding="ascii", errors="ignore") as f:
            # Google Drive may mount a little after login: wait up to five minutes for the program file.
            f.write('@echo off\r\nset /a n=0\r\n:wait\r\nif exist "%s" goto run\r\nset /a n+=1\r\n'
                    'if %%n%% geq 60 exit /b\r\ntimeout /t 5 /nobreak >nul\r\ngoto wait\r\n:run\r\n'
                    'start "" "%s" "%s"\r\n' % (me, exe, me))
        notes.append("autostart on")
        old = os.path.join(startup, "LiveEar.bat")
        if os.path.exists(old):
            os.remove(old)
            notes.append("old standby removed from startup")
    except Exception as e:
        notes.append("autostart failed: " + str(e)[:60])
    # 2. stop the old standby ear if it is still running
    try:
        r = ps("$p = Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'live_ear\\.py' -and $_.CommandLine -match '--standby' }; "
               "$p | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }; ($p | Measure-Object).Count")
        n = (r.stdout or "0").strip().splitlines()[-1:] or ["0"]
        if n[0] not in ("", "0"):
            notes.append("old standby stopped")
    except Exception:
        pass
    # 3. old program copies on the desktop and in downloads go to the recycle bin
    try:
        here = os.path.dirname(os.path.abspath(__file__)).replace("'", "''")
        r = ps("Add-Type -AssemblyName Microsoft.VisualBasic; $out=@(); "
               "foreach($d in @([Environment]::GetFolderPath('Desktop'), (Join-Path $env:USERPROFILE 'Downloads'))){ "
               " if(-not (Test-Path $d)){continue}; "
               " Get-ChildItem -LiteralPath $d -Force | Where-Object { $_.Name -like 'LiveEar_PC*' } | ForEach-Object { "
               "  if($_.FullName -eq '" + here + "' -or ('" + here + "').StartsWith($_.FullName + '\\')){ return }; "
               "  if($_.PSIsContainer){ [Microsoft.VisualBasic.FileIO.FileSystem]::DeleteDirectory($_.FullName,'OnlyErrorDialogs','SendToRecycleBin') } "
               "  else { [Microsoft.VisualBasic.FileIO.FileSystem]::DeleteFile($_.FullName,'OnlyErrorDialogs','SendToRecycleBin') }; "
               "  $out += $_.Name } }; $out -join ', '", timeout=120)
        moved = (r.stdout or "").strip()
        notes.append("recycled: " + moved if moved else "nothing to clean")
    except Exception as e:
        notes.append("cleanup failed: " + str(e)[:60])
    append(f"[{now()}] ===== SETUP {'; '.join(notes)} =====")


def mic_setup():
    """Make the real microphone the default at full level, silently, on every start."""
    if os.name != "nt":
        return
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mic_boost.ps1")
    if not os.path.isfile(script):
        return
    now = datetime.datetime.now().strftime("%H:%M:%S")
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-WindowStyle", "Hidden",
                            "-File", script, "-Mode", "silent"], capture_output=True, text=True,
                           timeout=60, creationflags=0x08000000)
        out = [l for l in (r.stdout or "").splitlines() if l.strip()]
        err = [l for l in (r.stderr or "").splitlines() if l.strip()]
        last = out[-1] if out else (err[-1] if err else "no output")
        if last.startswith("MIC|"):
            _, name, old, new = (last.split("|") + ["", "", ""])[:4]
            append(f"[{now}] ===== MIC {name} level {old}% -> {new}% =====")
        else:
            append(f"[{now}] ===== MIC setup note: {last[:120]} =====")
    except Exception as e:
        append(f"[{now}] ===== MIC setup failed: {str(e)[:100]} =====")


def open_window():
    url = f"http://127.0.0.1:{PORT}/"
    for exe in (shutil.which("msedge"),
                os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"),
                os.path.expandvars(r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe")):
        if exe and os.path.isfile(exe):
            subprocess.Popen([exe, f"--app={url}", "--window-size=520,760"])
            return
    webbrowser.open(url)


class ExclusiveServer(ThreadingHTTPServer):
    # On Windows the default reuse flag lets several copies share one port silently.
    allow_reuse_address = False

    def server_bind(self):
        import socket
        if os.name == "nt" and hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


def kill_other_copies():
    """Stop every other running copy of this program, whatever its version."""
    if os.name != "nt":
        return 0
    try:
        r = ps("$me = %d; $p = Get-CimInstance Win32_Process | Where-Object { $_.ProcessId -ne $me -and $_.CommandLine -match 'ear_local\\.py' }; "
               "$p | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }; ($p | Measure-Object).Count" % os.getpid())
        n = (r.stdout or "0").strip().splitlines()
        return int(n[-1]) if n and n[-1].isdigit() else 0
    except Exception:
        return 0


def main():
    killed = kill_other_copies()
    if killed:
        time.sleep(1.5)
    server = None
    for attempt in range(6):
        try:
            server = ExclusiveServer(("127.0.0.1", PORT), Handler)
            break
        except OSError:
            # An older copy is still running in the background: the newest launch takes over.
            if attempt == 0:
                print("An older Live Ear is running. Replacing it with this version.", flush=True)
                try:
                    import urllib.request
                    req = urllib.request.Request(f"http://127.0.0.1:{PORT}/quit", data=b"{}", method="POST")
                    urllib.request.urlopen(req, timeout=3).read()
                except Exception:
                    pass
            time.sleep(1.5)
    if server is None:
        print("Port", PORT, "is busy and the old copy did not close. Opening its window.", flush=True)
        open_window()
        time.sleep(3)
        return
    print("Live Ear (PC)", VERSION, "| transcript:", OUT, flush=True)
    print("Running in the background. Close it from the button in its window.", flush=True)
    if killed:
        append(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] ===== SETUP stopped {killed} older running copies =====")
    threading.Thread(target=mic_setup, daemon=True).start()
    threading.Thread(target=pc_setup, daemon=True).start()
    threading.Thread(target=command_loop, args=(server,), daemon=True).start()
    threading.Thread(target=awake_loop, daemon=True).start()
    threading.Thread(target=fallback_loop, daemon=True).start()
    threading.Timer(1.0, open_window).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        status("web-off")


if __name__ == "__main__":
    main()
