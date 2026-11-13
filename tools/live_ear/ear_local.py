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
VERSION = "web-2026-11-13"


def find_drive():
    for d in "GHIJKLMNOPEFD":
        p = d + ":\\My Drive"
        if os.path.isdir(p):
            return p
    p = os.path.join(os.path.expanduser("~"), "Desktop")
    return p if os.path.isdir(p) else os.path.expanduser("~")


DRIVE = find_drive()
OUT = os.path.join(DRIVE, "COP31_live.txt")
STATUS = os.path.join(DRIVE, "COP31_live_status.txt")
LOCK = threading.Lock()
PENDING = []


def append(line):
    print(line, flush=True)
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
</style></head><body><div class="app">
<h1>الأذن الحية على الحاسوب</h1>
<div class="row">
 <label>لغة القاعة <select id="lang"><option value="en-US">English</option><option value="en-GB">English UK</option><option value="ar-IQ">العربية</option></select></label>
</div>
<button class="mic" id="mic">ابدأ السماع</button>
<div class="st">الحالة: <b id="state">متوقفة</b> | الأسطر: <b id="n">0</b> | آخر كلام: <b id="last">لا يوجد</b></div>
<div class="st warn" id="warn" hidden></div>
<div class="st">يمكنك تصغير هذه النافذة بعد البدء. النص يكتب في COP31_live.txt على Drive.</div>
<div class="tx" id="tx"></div>
</div>
<script>
const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
const $=id=>document.getElementById(id);
let rec=null, want=false, n=0, partialEl=null, lastErr="", restarts=0, ctx=null;
try{$("lang").value=localStorage.getItem("lang")||"en-US"}catch(e){}
$("lang").onchange=()=>{try{localStorage.setItem("lang",$("lang").value)}catch(e){} if(want){rec&&rec.stop()}};
const pad=x=>String(x).padStart(2,"0");
const hms=d=>pad(d.getHours())+":"+pad(d.getMinutes())+":"+pad(d.getSeconds());
function post(path,obj){return fetch(path,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(obj)}).catch(()=>{})}
function beep(){try{ctx=ctx||new AudioContext();[0,.35].forEach(o=>{const s=ctx.createOscillator(),g=ctx.createGain();s.frequency.value=880;g.gain.value=.15;s.connect(g);g.connect(ctx.destination);s.start(ctx.currentTime+o);s.stop(ctx.currentTime+o+.18)})}catch(e){}}
function warn(t){$("warn").textContent=t;$("warn").hidden=!t}
function show(time,text,partial){
  if(partial){ if(!partialEl){partialEl=document.createElement("div");partialEl.className="p";$("tx").appendChild(partialEl)} partialEl.textContent=text; }
  else{ if(partialEl){partialEl.remove();partialEl=null}
    const d=document.createElement("div"); const t=document.createElement("time"); t.textContent=time; d.append(t,document.createTextNode(text)); $("tx").appendChild(d);
    while($("tx").children.length>300) $("tx").firstChild.remove(); }
  $("tx").scrollTop=$("tx").scrollHeight;
}
function setUi(){ $("mic").textContent=want?"أوقف السماع":"ابدأ السماع"; $("mic").classList.toggle("on",want); }
function build(){
  rec=new SR(); rec.continuous=true; rec.interimResults=true; rec.lang=$("lang").value; rec.maxAlternatives=1;
  rec.onstart=()=>{ $("state").textContent="تسمع الآن"; warn(""); restarts=0; };
  rec.onresult=e=>{
    let interim="";
    for(let i=e.resultIndex;i<e.results.length;i++){
      const r=e.results[i], text=r[0].transcript.trim();
      if(!text) continue;
      if(r.isFinal){ const now=hms(new Date()); n++; $("n").textContent=n; $("last").textContent=now; show(now,text,false); post("/line",{time:now,text}); }
      else interim+=text+" ";
    }
    if(interim) show("",interim.trim(),true);
  };
  rec.onerror=e=>{ lastErr=e.error;
    if(e.error==="not-allowed"||e.error==="service-not-allowed"){ want=false; setUi(); warn("الميكروفون ممنوع. اسمح به من أيقونة القفل بجانب العنوان ثم ابدأ من جديد."); beep(); post("/status",{state:"blocked"}); }
    else if(e.error==="network"){ warn("انقطع الإنترنت، سيعاد الاتصال تلقائيا."); }
    else if(e.error==="audio-capture"){ warn("لا يوجد ميكروفون يعمل. تأكد من اختيار الميكروفون الصحيح."); }
  };
  rec.onend=()=>{
    $("state").textContent=want?"يعاد التشغيل":"متوقفة";
    if(!want){ post("/status",{state:"stopped"}); return; }
    restarts++;
    if(restarts===8){ beep(); warn("السماع ينقطع مرارا. تأكد من الإنترنت والميكروفون."); }
    setTimeout(()=>{ if(want){ try{ rec.lang=$("lang").value; rec.start(); }catch(err){} } }, restarts>5?3000:250);
  };
}
$("mic").onclick=()=>{
  if(!SR){ warn("هذا المتصفح لا يدعم التعرف على الكلام. افتح الصفحة في Edge أو Chrome."); return; }
  try{ctx=ctx||new AudioContext();ctx.resume()}catch(e){}
  if(want){ want=false; setUi(); rec&&rec.stop(); post("/stop",{}); return; }
  want=true; setUi(); if(!rec) build(); rec.lang=$("lang").value;
  post("/start",{lang:$("lang").value});
  try{ rec.start(); }catch(e){}
};
setInterval(()=>{ post("/status",{state: want?($("state").textContent==="تسمع الآن"?"listening":"restarting"):"stopped"}); },20000);
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
        self._ok(PAGE.encode("utf-8"), "text/html")

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        try:
            data = json.loads(self.rfile.read(n) or b"{}")
        except ValueError:
            data = {}
        now = datetime.datetime.now().strftime("%H:%M:%S")
        if self.path == "/line":
            text = " ".join(str(data.get("text", "")).split())
            if text:
                append(f"[{data.get('time') or now}] {text}")
        elif self.path == "/start":
            append(f"[{now}] ===== START {datetime.date.today()} web lang={data.get('lang', '')} v={VERSION} =====")
            status("web-listening")
        elif self.path == "/stop":
            append(f"[{now}] ===== STOP =====")
            status("web-stopped")
        elif self.path == "/status":
            status("web-" + str(data.get("state", "unknown"))[:20])
        self._ok()


def open_window():
    url = f"http://127.0.0.1:{PORT}/"
    for exe in (shutil.which("msedge"),
                os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"),
                os.path.expandvars(r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe")):
        if exe and os.path.isfile(exe):
            subprocess.Popen([exe, f"--app={url}", "--window-size=520,760"])
            return
    webbrowser.open(url)


def main():
    try:
        server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    except OSError:
        print("Live Ear is already running. Opening its window.", flush=True)
        open_window()
        time.sleep(3)
        return
    print("Live Ear (PC)", VERSION, "| transcript:", OUT, flush=True)
    print("Keep this black window open. You may minimize it.", flush=True)
    threading.Timer(1.0, open_window).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        status("web-off")


if __name__ == "__main__":
    main()
