"""Live Ear (PC): the browser's own speech recognition, kept alive while minimized.

Run:  python ear_local.py
It starts a tiny local server on http://127.0.0.1:8765 and opens it in Edge
as a small app window. Press the start button once. Every settled sentence is
appended to COP31_live.txt in Google Drive, and a heartbeat goes to
COP31_live_status.txt every 20 seconds. Standard library only: nothing to
install beyond Python itself.
"""
import datetime, json, os, queue, shutil, subprocess, sys, threading, time, webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    import ear_logic as L  # writer with retry, audio store, gap backfill, speaker tags
except ImportError:
    with open(os.path.join(os.path.expanduser("~"), "LiveEar_PC.log"), "a", encoding="utf-8") as _f:
        _f.write("ear_logic.py is missing: copy it next to ear_local.py\n")
    raise SystemExit("ear_logic.py is missing: copy it next to ear_local.py")

PORT = 8765
VERSION = "web-2026-11-24d"


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
SESS_DIR = os.path.join(os.path.expanduser("~"), "LiveEar_Sessions")
CURRENT = {"path": None}
LAST = {"path": None}  # the most recent session file, kept after stop so a late summary can still name it
PAGE_URL = "https://claude.ai/artifact/9ag5mqwy8LRaGpwUmwi3za"


def safe_name(name):
    keep = "".join(c if (c.isalnum() or c in " -_.") else " " for c in name).strip()
    return " ".join(keep.split())[:60] or "session"


def new_session(name):
    os.makedirs(SESS_DIR, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y-%m-%d_%H%M")
    CURRENT["path"] = LAST["path"] = os.path.join(SESS_DIR, f"{stamp}_{safe_name(name)}.txt")


def rename_session(name):
    """Give a session started without a name the name the summary inferred from its content."""
    path = LAST["path"]
    if not path or not path.endswith("_session.txt") or not os.path.exists(path):
        return False
    new = path[:-len("session.txt")] + safe_name(name) + ".txt"
    try:
        os.replace(path, new)
    except OSError:
        return False
    if CURRENT["path"] == path:
        CURRENT["path"] = new
    LAST["path"] = new
    return True


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
        if not fn.endswith(".txt") or fn.endswith("_دقيق.txt"):
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
AWAKE = {"on": False, "work": 0}   # work: background transcription jobs still running after stop


def awake_loop():
    while True:
        if (AWAKE["on"] or AWAKE["work"] > 0) and os.name == "nt":
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
    arabic = rec_lang().startswith("ar")
    model = ["--model", "small", "--lang", "ar"] if arabic else ["--model", "small.en"]
    append(f"[{now}] ===== FALLBACK START ({why}) {model[1]} =====")
    flags = 0x08000000 if os.name == "nt" else 0  # CREATE_NO_WINDOW
    try:
        FALLBACK["proc"] = subprocess.Popen([python_exe(), script] + model + ["--drive", DRIVE],
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


WRITER = L.Writer(OUT)  # lines wait here while Drive is unavailable; a flusher retries every 5 s
ARCHIVE = os.path.join(DRIVE, "COP31_live_archive")


def rotate_transcript():
    """A fresh COP31_live.txt each day: earlier days go to COP31_live_archive on Drive."""
    moved = WRITER.rotate(ARCHIVE)
    if moved:
        append(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] ===== ARCHIVE earlier lines moved to COP31_live_archive/{os.path.basename(moved)} =====")


def append(line):
    print(line, flush=True)
    to_session(line)      # the PC copy first: it never depends on Drive
    WRITER.append(line)


# ---------- room audio kept on the PC, and backfill of gaps ----------
HERE = os.path.dirname(os.path.abspath(__file__))
STORE = L.AudioStore(os.path.join(SESS_DIR, "audio"))
BACKFILL = {"b": None}
REC = {"on": False, "note": ""}


SESSION = {"lang": "auto", "cur": "en-US", "start": "", "last": "", "arabic": False}  # the language chosen in the window, and the one in use when it is auto


def rec_lang():
    return SESSION["cur"] if SESSION["lang"] == "auto" else SESSION["lang"]


def backfill_setup():
    tr = L.language_transcriber(rec_lang, threads=2)
    if tr is None:
        append(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] ===== BACKFILL unavailable: faster-whisper not installed =====")
        return
    BACKFILL["b"] = L.Backfiller(STORE, tr, append)
    BACKFILL["b"].run_forever()


def recorder_loop():
    """Keeps the room audio on the PC while a session runs, independent of the browser."""
    try:
        import sounddevice as sd
    except ImportError:
        REC["note"] = "sounddevice not installed"
        return
    blocks = queue.Queue()
    while True:
        if not CURRENT["path"]:
            time.sleep(1)
            continue
        try:
            def cb(indata, frames, t, st):
                blocks.put((indata[:, 0].copy(), time.time()))
            with sd.InputStream(samplerate=STORE.rate, channels=1, dtype="float32",
                                blocksize=STORE.rate // 10, callback=cb):
                REC["on"] = True
                while CURRENT["path"]:
                    try:
                        b, t = blocks.get(timeout=1)
                    except queue.Empty:
                        continue
                    STORE.write(b, end_time=t)
        except Exception as e:
            REC["note"] = str(e)[:80]
            time.sleep(5)  # the microphone dropped: try again
        finally:
            REC["on"] = False
            STORE.close()


# ---------- automatic language: the room audio decides English or Arabic ----------
LANG = {"w": None, "pending": None, "note": None, "noted": False, "at": 0.0, "logged": 0, "detect": None}


def lang_loop():
    detect = L.whisper_language_detector("base", threads=1)
    LANG["detect"] = detect
    if detect is not None:
        LANG["w"] = L.LanguageWatcher(STORE, detect)
        try:  # load the model now, so the first switch in a session is not delayed by loading it
            import numpy as np
            detect(np.zeros(STORE.rate, np.float32))
        except Exception:
            pass
    while True:
        time.sleep(5)  # two readings in a row decide a switch: about ten seconds
        if not CURRENT["path"] or SESSION["lang"] != "auto":
            continue
        if LANG["w"] is None:
            if not LANG["noted"]:
                LANG["noted"] = True
                LANG["note"] = "no-detector"
                append(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] ===== LANG auto unavailable: faster-whisper not installed, staying on {rec_lang()} =====")
            continue
        if not REC["on"]:
            continue
        try:
            r = LANG["w"].step()
        except Exception as e:
            append(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] ===== LANG error: {str(e)[:80]} =====")
            time.sleep(50)
            continue
        last = LANG["w"].last
        if not r:
            # a reading that disagrees with the language in use is written down (20 per session), to see why no switch came
            if last and last[0] != LANG["w"].current and LANG["logged"] < 20:
                LANG["logged"] += 1
                append(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] ===== LANG? heard {last[0]} {last[1]:.2f} of English and Arabic, in use {SESSION['cur']} =====")
            continue
        lang, since = r
        SESSION["cur"] = L.AUTO_LANGS[lang]
        SESSION["arabic"] = SESSION["arabic"] or lang == "ar"
        LANG["pending"], LANG["at"] = SESSION["cur"], time.time()
        append(f"[{L.hms(since)}] ===== LANG {SESSION['cur']} auto =====")
        if BACKFILL["b"]:
            # the words spoken before the window switched are recovered from the stored audio
            BACKFILL["b"].enqueue(since - 2, time.time() + 6, lang)


# ---------- accurate pass: after an Arabic session, the whole recording is transcribed again ----------
ACCURATE = {"q": queue.Queue(), "tr": None, "tried": False}


def queue_accurate():
    """Called at stop: a session in which Arabic was used gets an accurate transcript."""
    if not (SESSION["arabic"] and SESSION["start"]):
        return
    job = {"start": L.clock_to_ts(SESSION["start"]), "end": time.time(), "hms": SESSION["start"], "path": LAST["path"]}
    append(f"[{L.hms(job['end'])}] ===== ACCURATE PENDING session={job['hms']} =====")
    ACCURATE["q"].put(job)


def background_priority(low):
    """Below-normal priority while the large model works, so Edge, Drive and the window stay responsive."""
    if os.name != "nt":
        return
    try:
        import ctypes
        k = ctypes.windll.kernel32
        k.SetPriorityClass(k.GetCurrentProcess(), 0x00004000 if low else 0x00000020)  # BELOW_NORMAL / NORMAL
    except Exception:
        pass


def accurate_loop():
    while True:
        job = ACCURATE["q"].get()
        AWAKE["work"] += 1          # the PC must not sleep before the accurate pass ends
        background_priority(True)
        try:
            accurate_job(job)
        finally:
            AWAKE["work"] -= 1
            background_priority(False)


def accurate_job(job):
    if not ACCURATE["tried"]:
        ACCURATE["tried"] = True
        # half of the logical processors: on 24/11 every core made the PC stop syncing Drive for an hour
        ACCURATE["tr"] = L.accurate_transcriber(threads=max(2, (os.cpu_count() or 4) // 2))
    if ACCURATE["tr"] is None:
        append(f"[{L.hms(time.time())}] ===== ACCURATE unavailable: faster-whisper not installed =====")
        return
    t0 = time.time()
    try:
        tracker = L.SpeakerTracker(L.load_aliases(os.path.join(HERE, "speakers.json")))
        lines = L.accurate_pass(STORE, job["start"], job["end"], ACCURATE["tr"], tracker)
    except Exception as e:
        append(f"[{L.hms(time.time())}] ===== ACCURATE error: {str(e)[:80]} =====")
        return
    mins = round((time.time() - t0) / 60)
    audio_mins = round((job["end"] - job["start"]) / 60, 1)
    block = [f"[{job['hms']}] ===== ACCURATE START session={job['hms']} model={L.ACCURATE_MODEL} ====="] + lines + \
            [f"[{L.hms(job['end'])}] ===== ACCURATE END session={job['hms']} {len(lines)} سطر في {mins} دقيقة لصوت {audio_mins} دقيقة ====="]
    WRITER.append_many(block)   # one block on Drive: no live line of a later session falls inside it
    if job["path"]:
        try:
            with open(job["path"][:-4] + "_دقيق.txt", "w", encoding="utf-8") as f:
                f.write("\n".join(block) + "\n")
        except OSError:
            pass


# ---------- speaker tags and the group alert ----------
TRACKER = {"t": L.SpeakerTracker(L.load_aliases(os.path.join(HERE, "speakers.json")))}
ALERT = {"who": "", "at": 0.0, "time": "", "sent": True}


def raise_alert(who, when):
    ALERT.update(who=who, at=time.time(), time=when, sent=False)
    append(f"[{when}] ===== ALERT {who} =====")


def status(state):
    extra = ""
    if ALERT["who"] and time.time() - ALERT["at"] < 600:
        extra = f" alert={ALERT['who']}@{ALERT['time']}"
    try:
        with open(STATUS, "w", encoding="utf-8") as f:
            f.write(f"{state} {datetime.datetime.now().isoformat(timespec='seconds')}{extra}\n")
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
.tx div{padding:4px 0;border-bottom:1px solid var(--line);unicode-bidi:plaintext}
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
#sname:focus::placeholder{color:transparent}
</style></head><body><div class="app">
<h1>الأذن الحية على الحاسوب</h1>
<div class="row">
 <label>اسم الجلسة <input id="sname" placeholder="مثلا Article 6.2 informals" style="font:inherit;border-radius:8px;border:1px solid var(--line);background:var(--panel);color:var(--fg);padding:9px 10px;min-width:0;width:15em;max-width:100%"></label>
 <label>لغة القاعة <select id="lang"><option value="auto">تلقائي</option><option value="en-US">English</option><option value="en-GB">English UK</option><option value="ar-IQ">العربية (العراق)</option><option value="ar-SA">العربية (الفصحى)</option></select></label>
</div>
<button class="mic" id="mic">ابدأ السماع</button>
<div class="st">الحالة: <b id="state">متوقفة</b> | الأسطر: <b id="n">0</b> | آخر كلام: <b id="last">لا يوجد</b> | اللغة: <b id="lng">تلقائي</b></div>
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
// the window always opens on automatic language: a fixed language is chosen per session when wanted
let autoLang="en-US"; try{autoLang=localStorage.getItem("ear.autoLang")||"en-US"}catch(e){}
const LANG_NAMES={"en-US":"الإنكليزية","en-GB":"الإنكليزية","ar-IQ":"العربية","ar-SA":"العربية الفصحى"};
function recLang(){ return $("lang").value==="auto" ? autoLang : $("lang").value; }
function showLang(){ $("lng").textContent = $("lang").value==="auto" ? (want ? LANG_NAMES[autoLang]+" (تلقائي)" : "تلقائي") : LANG_NAMES[$("lang").value]; }
$("lang").value="auto";
$("lang").onchange=()=>{ showLang(); if(want){ post("/lang",{lang:$("lang").value, cur:recLang()}); forceRestart("lang"); } };
$("sname").addEventListener("focus",()=>$("sname").select());
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
  rec=new SR(); rec.continuous=true; rec.interimResults=true; rec.lang=recLang(); rec.maxAlternatives=1;
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
    try{ rec.lang=recLang(); rec.start(); }catch(err){ forceRestart("start-failed"); }
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
function stopListening(){ if(!want) return; want=false; setUi(); showLang(); try{rec&&rec.stop()}catch(e){} post("/stop",{}); }
function startListening(){
  if(!SR || want) return;
  try{ctx=ctx||new AudioContext();ctx.resume()}catch(e){}
  want=true; setUi(); keepAwake();
  post("/start",{lang:$("lang").value, cur:recLang(), name:$("sname").value.trim()}); showLang();
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
    if(c.alert){ warn(c.alert==="lmdc"?"تتكلم الآن مجموعة البلدان النامية المتشابهة التفكير":"تتكلم الآن المجموعة العربية"); beep(); setTimeout(()=>warn(""),60000); }
    if(c.lang && c.lang!==autoLang){ autoLang=c.lang; try{localStorage.setItem("ear.autoLang",autoLang)}catch(e){} showLang(); if(want && $("lang").value==="auto") forceRestart("lang"); }
    if(c.note==="no-detector") warn("التحديد التلقائي للغة يحتاج برنامج faster-whisper على الحاسوب، فالسماع مستمر بـ"+LANG_NAMES[autoLang]+". إن كانت الجلسة بلغة أخرى فاخترها من القائمة.");
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
  post("/status",{state: failing?"failing":($("state").textContent==="تسمع الآن"?"listening":"restarting"), ok:!failing, cur:recLang()});
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
            if LANG["pending"]:
                c["lang"] = LANG["pending"]
                LANG["pending"] = None
            if LANG["note"]:
                c["note"] = LANG["note"]
                LANG["note"] = None
            if not ALERT["sent"]:
                c["alert"] = ALERT["who"]
                ALERT["sent"] = True
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
                when = data.get("time") or now
                tagged, alert = TRACKER["t"].tag(text)
                SESSION["last"] = when
                append(f"[{when}] {tagged}")
                if alert:
                    raise_alert(alert, when)
        elif self.path == "/gap":
            when, secs, why = data.get("time") or now, int(data.get("secs") or 0), str(data.get("why") or "")[:60]
            append(f"[{when}] ===== GAP {secs} ثانية, {why} =====")
            if BACKFILL["b"] and REC["on"] and L.needs_backfill(why, secs):
                start = L.clock_to_ts(when)
                BACKFILL["b"].enqueue(start, start + secs)
        elif self.path == "/start":
            name = " ".join(str(data.get("name") or "").split())[:80]
            rotate_transcript()
            new_session(name or "session")
            SESSION["lang"] = str(data.get("lang") or "auto")
            SESSION["cur"] = str(data.get("cur") or "en-US")
            LANG["pending"], LANG["noted"], LANG["logged"] = None, False, 0
            SESSION["arabic"] = SESSION["cur"].startswith("ar") or SESSION["lang"].startswith("ar")
            SESSION["start"], SESSION["last"] = now, now
            if LANG["w"]:
                LANG["w"].reset("ar" if SESSION["cur"].startswith("ar") else "en")
            TRACKER["t"] = L.SpeakerTracker(L.load_aliases(os.path.join(HERE, "speakers.json")))
            threading.Thread(target=STORE.prune, daemon=True).start()
            AWAKE["on"] = True
            PAGE_STATE.update(ok=True, seen=time.time(), bad_since=0.0, good_since=0.0)
            append(f"[{now}] ===== START {datetime.date.today()} web lang={SESSION['lang']} cur={SESSION['cur']} v={VERSION} name={name} =====")
            status("web-listening")
        elif self.path == "/stop":
            append(f"[{now}] ===== STOP =====")
            CURRENT["path"] = None
            if REC["on"] or STORE.segments():
                queue_accurate()
            AWAKE["on"] = False
            stop_fallback("stopped")
            status("web-stopped")
        elif self.path == "/lang":
            # the language list was changed in the window: follow it, and in auto mode start from the language in use
            SESSION["lang"] = str(data.get("lang") or "auto")
            SESSION["cur"] = str(data.get("cur") or SESSION["cur"])
            SESSION["arabic"] = SESSION["arabic"] or SESSION["cur"].startswith("ar") or SESSION["lang"].startswith("ar")
            if LANG["w"]:
                LANG["w"].reset("ar" if SESSION["cur"].startswith("ar") else "en")
            if CURRENT["path"]:
                append(f"[{now}] ===== LANG {SESSION['lang']} chosen in the window, in use {SESSION['cur']} =====")
        elif self.path == "/status":
            PAGE_STATE["seen"] = time.time()
            cur = str(data.get("cur") or "")
            w = LANG["w"]
            if cur and SESSION["lang"] == "auto" and w and not LANG["pending"] and time.time() - LANG["at"] > 30:
                fam = "ar" if cur.startswith("ar") else "en"
                if fam != w.current:  # the window and the watcher disagree: trust what the window really uses
                    w.current = fam
                    SESSION["cur"] = cur
            PAGE_STATE["ok"] = data.get("ok", True) is not False
            state = str(data.get("state", "unknown"))[:20]
            if FALLBACK["proc"]:
                state += "+fallback"
            status("web-" + state)
        elif self.path == "/open":
            what = "reply" if data.get("what") == "reply" else "summary"
            # the page waits until Drive has brought this session up to its last line
            tag = ("-" + SESSION["start"].replace(":", "") + "-" + SESSION["last"].replace(":", "")) if SESSION["start"] else ""
            webbrowser.open(PAGE_URL + "#" + what + tag)
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
CMD_FILES = {"start": "COP31_ear_START.txt", "stop": "COP31_ear_STOP.txt", "quit": "COP31_ear_QUIT.txt",
             "name": "COP31_ear_NAME.txt"}  # NAME: written by the summary page for a session started without a name


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
            if cmd == "name":
                if name and rename_session(name):
                    append(f"[{now}] ===== NAME {name} =====")
                continue
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
        # the restart loop (run_standby.bat) goes first, or it starts the standby again after 15 seconds
        r = ps("$p = Get-CimInstance Win32_Process | Where-Object { $_.ProcessId -ne $PID -and ($_.CommandLine -match 'run_standby\\.bat' -or ($_.CommandLine -match 'live_ear\\.py' -and $_.CommandLine -match '--standby')) }; "
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
        r = ps("$me = %d; $p = Get-CimInstance Win32_Process | Where-Object { $_.ProcessId -ne $me -and $_.ProcessId -ne $PID -and $_.CommandLine -match 'ear_local\\.py' }; "
               "$p | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }; ($p | Measure-Object).Count" % os.getpid())
        n = (r.stdout or "0").strip().splitlines()
        return int(n[-1]) if n and n[-1].isdigit() else 0
    except Exception:
        return 0


def main():
    rotate_transcript()   # first, before any startup line: an earlier day's file is archived under its own date
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
    WRITER.run_flusher(5.0)
    threading.Thread(target=recorder_loop, daemon=True).start()
    threading.Thread(target=backfill_setup, daemon=True).start()
    threading.Thread(target=lang_loop, daemon=True).start()
    threading.Thread(target=accurate_loop, daemon=True).start()
    threading.Timer(1.0, open_window).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        status("web-off")


if __name__ == "__main__":
    main()
