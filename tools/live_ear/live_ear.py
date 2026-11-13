"""Live ear: listens to the room microphone and writes a timestamped
transcript to a text file in Google Drive, offline, a few seconds behind speech.

Two modes:
  python live_ear.py             listen now until Ctrl+C (manual mode)
  python live_ear.py --standby   wait in the background, listen only while the
                                 Drive control file is named COP31_listen_ON.txt
                                 (the Live Follow page renames it)
Both modes write a heartbeat to COP31_live_status.txt every 20 seconds, and
both restart the microphone by themselves when it stops delivering sound
(after the computer sleeps, or when the device drops).

Options:
  --model base.en|small.en   speed versus accuracy (default base.en)
  --lang en|ar|auto          spoken language (default en)
  --device N                 microphone number from --list
  --list                     list audio input devices and exit
  --file clip.wav            transcribe a 16 kHz mono wav instead (test)
  --drive PATH               Drive folder (default: first X:\\My Drive found)
"""
import argparse, os, queue, re, sys, threading, time, datetime
import numpy as np

VERSION = "2026-11-13b"
SR = 16000
BLOCK = 0.1            # seconds per audio block
SILENCE_END = 0.7      # seconds of silence that closes a phrase
MIN_PHRASE = 2.0       # seconds
MAX_PHRASE = 8.0       # seconds
POLL = 3               # seconds between control checks
BEAT = 20              # seconds between heartbeats
STALL = 15             # seconds without microphone sound before a restart
RETRY_MAX = 60         # longest wait between microphone restart attempts

# Phrases Whisper is known to invent from noise or silence.
JUNK = {
    "thanks for watching", "thank you for watching", "thanks for watching!",
    "please subscribe", "subscribe to my channel", "like and subscribe",
    "subtitles by the amara.org community", "you",
}


def now():
    return datetime.datetime.now().strftime("%H:%M:%S")


def find_drive(arg):
    if arg:
        return arg
    for d in "GHIJKLMNOPEFD":
        p = d + ":\\My Drive"
        if os.path.isdir(p):
            return p
    p = os.path.join(os.path.expanduser("~"), "Desktop")
    return p if os.path.isdir(p) else os.path.expanduser("~")


class Out:
    """Appends lines to the transcript. If Drive holds the file for a moment,
    lines wait in memory and go out with the next write."""

    def __init__(self, path):
        self.path = path
        self.lock = threading.Lock()
        self.pending = []

    def write(self, line):
        print(line, flush=True)
        with self.lock:
            self.pending.append(line)
            for _ in range(3):
                try:
                    with open(self.path, "a", encoding="utf-8") as f:
                        f.write("\n".join(self.pending) + "\n")
                        f.flush()
                        os.fsync(f.fileno())
                    self.pending = []
                    return
                except OSError as e:
                    err = e
                    time.sleep(0.5)
            print("write delayed:", err, flush=True)


# ---------- hallucination filter ----------

def _norm(w):
    return re.sub(r"[^\w']", "", w.lower())


def collapse_repeats(text, keep=1, min_run=3):
    """Collapse any 1 to 4 word group repeated min_run or more times in a row."""
    words = text.split()
    for n in (1, 2, 3, 4):
        out, i = [], 0
        while i < len(words):
            gram = [_norm(w) for w in words[i:i + n]]
            if len(gram) < n or not any(gram):
                out.append(words[i]); i += 1; continue
            j = i + n
            while [_norm(w) for w in words[j:j + n]] == gram:
                j += n
            reps = (j - i) // n
            if reps >= min_run:
                out.extend(words[i:i + n * keep])
                i = j
            else:
                out.append(words[i]); i += 1
        words = out
    return " ".join(words)


def clean(text, last):
    """Return cleaned text, or '' when the line is noise."""
    text = collapse_repeats(text.strip())
    plain = " ".join(_norm(w) for w in text.split()).strip()
    if not plain:
        return ""
    letters = re.sub(r"[^a-z\u0600-\u06ff]", "", plain)
    if len(letters) < 2:
        return ""
    if plain in JUNK:
        return ""
    # a line made of one or two letter tokens only (S. S. M.) is noise
    if all(len(w) <= 1 for w in plain.split()) and len(plain.split()) > 1:
        return ""
    if last and plain == last:
        return ""
    return text


def good_segment(s):
    if s.no_speech_prob > 0.6 and s.avg_logprob < -1.0:
        return False
    if s.compression_ratio > 2.4:
        return False
    if s.avg_logprob < -1.5:
        return False
    return True


def worker(model, lang, jobs, out):
    last = ""
    while True:
        item = jobs.get()
        if item is None:
            return
        stamp, audio = item
        try:
            segs, _ = model.transcribe(
                audio, language=None if lang == "auto" else lang,
                beam_size=1, vad_filter=True,
                vad_parameters={"min_silence_duration_ms": 500},
                condition_on_previous_text=False,
                compression_ratio_threshold=2.4,
                log_prob_threshold=-1.0,
                no_speech_threshold=0.6)
            text = " ".join(s.text.strip() for s in segs if good_segment(s)).strip()
        except Exception as e:  # keep listening whatever happens
            text = ""
            print("transcribe error:", e, flush=True)
        text = clean(text, last) if text else ""
        if text:
            last = " ".join(_norm(w) for w in text.split()).strip()
            out.write(f"[{stamp}] {text}")


# ---------- audio ----------

def chunker(blocks, jobs):
    buf, speech, silent, start = [], 0.0, 0.0, None
    level = 0.004  # adapts to room noise
    for b in blocks:
        rms = float(np.sqrt(np.mean(b * b)) + 1e-9)
        loud = rms > level * 2.5
        if not loud:
            level = 0.95 * level + 0.05 * rms
        if loud:
            if start is None:
                start = now()
            speech += BLOCK
            silent = 0.0
        elif start is not None:
            silent += BLOCK
        if start is not None:
            buf.append(b)
        dur = len(buf) * BLOCK
        if start is not None and ((silent >= SILENCE_END and speech >= MIN_PHRASE) or dur >= MAX_PHRASE):
            jobs.put((start, np.concatenate(buf)))
            buf, speech, silent, start = [], 0.0, 0.0, None
        elif start is not None and silent >= SILENCE_END * 3:
            buf, speech, silent, start = [], 0.0, 0.0, None
    if buf and speech >= MIN_PHRASE:
        jobs.put((start or now(), np.concatenate(buf)))


def mic_blocks(device, stop, alive):
    import sounddevice as sd
    q = queue.Queue()

    def cb(indata, frames, t, status):
        q.put(indata[:, 0].copy())

    with sd.InputStream(samplerate=SR, channels=1, dtype="float32",
                        blocksize=int(SR * BLOCK), device=device, callback=cb):
        while not stop.is_set():
            try:
                b = q.get(timeout=0.5)
            except queue.Empty:
                continue
            alive()
            yield b


def file_blocks(path):
    import wave
    with wave.open(path) as w:
        audio = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
    n = int(SR * BLOCK)
    for i in range(0, len(audio), n):
        yield audio[i:i + n]


class Listener:
    """One listening period: microphone -> phrases -> transcript.
    check() restarts the microphone when it dies or goes quiet."""

    def __init__(self, device, jobs, out, model_name):
        self.device, self.jobs, self.out = device, jobs, out
        self.model_name = model_name
        self.stop = threading.Event()
        self.thread = None
        self.active = False
        self.last_sound = 0.0
        self.spawned = 0.0
        self.next_try = 0.0
        self.wait = 5
        self.failing = False

    def _touch(self):
        self.last_sound = time.time()

    def _spawn(self):
        self.stop = threading.Event()
        self.spawned = time.time()
        self.thread = threading.Thread(target=self._run, args=(self.stop,), daemon=True)
        self.thread.start()

    def _run(self, stop):
        try:
            chunker(mic_blocks(self.device, stop, self._touch), self.jobs)
        except Exception as e:
            print("microphone error:", e, flush=True)

    def _kill(self):
        self.stop.set()
        if self.thread:
            self.thread.join(timeout=5)
        self.thread = None

    def start(self, label=""):
        self.active = True
        self.wait = 5
        self.failing = False
        self.out.write(f"[{now()}] ===== START {datetime.date.today()} {label} "
                       f"model={self.model_name} v={VERSION} =====")
        self._spawn()

    def running(self):
        return self.active

    def healthy(self):
        return (self.thread is not None and self.thread.is_alive()
                and time.time() - max(self.last_sound, self.spawned) < STALL)

    def check(self):
        """Called every few seconds by the main loop."""
        if not self.active:
            return
        alive = self.thread is not None and self.thread.is_alive()
        if self.failing and alive and self.last_sound > self.spawned:
            self.failing = False
            self.wait = 5
            self.out.write(f"[{now()}] ===== RESUMED =====")
            return
        if self.healthy() or time.time() < self.next_try:
            return
        if not self.failing:
            self.failing = True
            why = "microphone stopped" if not (self.thread and self.thread.is_alive()) else "no sound from microphone"
            self.out.write(f"[{now()}] ===== RESTART ({why}) =====")
        print(f"Restarting microphone (next try in {self.wait}s if it fails)...", flush=True)
        self._kill()
        self._spawn()
        self.next_try = time.time() + self.wait
        self.wait = min(self.wait * 2, RETRY_MAX)

    def state(self):
        if not self.active:
            return "standby"
        return "restarting" if self.failing else "listening"

    def end(self):
        self.active = False
        self._kill()
        self.out.write(f"[{now()}] ===== STOP =====")


def heartbeat(path, state):
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"{state} {datetime.datetime.now().isoformat(timespec='seconds')}\n")
    except OSError as e:
        print("status error:", e, flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out")
    ap.add_argument("--drive")
    ap.add_argument("--model", default="base.en")
    ap.add_argument("--lang", default="en")
    ap.add_argument("--device", type=int, default=None)
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--file")
    ap.add_argument("--standby", action="store_true")
    a = ap.parse_args()
    if a.list:
        import sounddevice as sd
        print(sd.query_devices())
        return
    drive = find_drive(a.drive)
    out = Out(a.out or os.path.join(drive, "COP31_live.txt"))
    on_flag = os.path.join(drive, "COP31_listen_ON.txt")
    status = os.path.join(drive, "COP31_live_status.txt")
    print("Live Ear", VERSION, "| transcript:", out.path, flush=True)

    from faster_whisper import WhisperModel
    if a.lang != "en" and a.model.endswith(".en"):
        a.model = a.model[:-3]
    print("Loading model", a.model, "...", flush=True)
    model = WhisperModel(a.model, device="cpu", compute_type="int8",
                         cpu_threads=os.cpu_count() or 4)
    jobs = queue.Queue()
    threading.Thread(target=worker, args=(model, a.lang, jobs, out), daemon=True).start()

    if a.file:
        out.write(f"[{now()}] ===== START {datetime.date.today()} test model={a.model} v={VERSION} =====")
        chunker(file_blocks(a.file), jobs)
        jobs.put(None)
        time.sleep(0.2)
        while not jobs.empty():
            time.sleep(0.2)
        time.sleep(3)
        out.write(f"[{now()}] ===== STOP =====")
        return

    ear = Listener(a.device, jobs, out, a.model)
    mode = "standby" if a.standby else "manual"
    if a.standby:
        print("Standby. Waiting for the Live Follow page. Close this window to quit.", flush=True)
    else:
        ear.start("manual")
        print("Listening. Press Ctrl+C to stop.", flush=True)

    last_beat = 0
    try:
        while True:
            if a.standby:
                want = os.path.exists(on_flag)
                if want and not ear.running():
                    ear.start("live-follow")
                elif not want and ear.running():
                    ear.end()
            ear.check()
            if time.time() - last_beat >= BEAT:
                heartbeat(status, f"{mode}-{ear.state()} model={a.model}")
                last_beat = time.time()
            time.sleep(POLL)
    except KeyboardInterrupt:
        if ear.running():
            ear.end()
        heartbeat(status, f"{mode}-off model={a.model}")


if __name__ == "__main__":
    main()
