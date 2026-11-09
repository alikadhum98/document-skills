"""Live ear: listens to the room microphone and writes a timestamped
transcript to a text file in Google Drive, offline, a few seconds behind speech.

Two modes:
  python live_ear.py             listen now until Ctrl+C (manual mode)
  python live_ear.py --standby   wait in the background, listen only while the
                                 Drive control file is named COP31_listen_ON.txt
                                 (the Live Follow page renames it), and write a
                                 heartbeat to COP31_live_status.txt
Options:
  --model base.en|small.en   speed versus accuracy (default base.en)
  --lang en|ar|auto          spoken language (default en)
  --device N                 microphone number from --list
  --list                     list audio input devices and exit
  --file clip.wav            transcribe a 16 kHz mono wav instead (test)
  --drive PATH               Drive folder (default: first X:\\My Drive found)
"""
import argparse, os, queue, sys, threading, time, datetime
import numpy as np

SR = 16000
BLOCK = 0.1            # seconds per audio block
SILENCE_END = 0.7      # seconds of silence that closes a phrase
MIN_PHRASE = 2.0       # seconds
MAX_PHRASE = 8.0       # seconds
POLL = 3               # seconds between control checks
BEAT = 20              # seconds between heartbeats


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
    def __init__(self, path):
        self.path = path
        self.lock = threading.Lock()

    def write(self, line):
        with self.lock:
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(line + "\n")
                f.flush()
                os.fsync(f.fileno())
        print(line, flush=True)


def worker(model, lang, jobs, out):
    while True:
        item = jobs.get()
        if item is None:
            return
        stamp, audio = item
        try:
            segs, _ = model.transcribe(audio, language=None if lang == "auto" else lang,
                                       beam_size=1, vad_filter=True,
                                       condition_on_previous_text=False)
            text = " ".join(s.text.strip() for s in segs).strip()
        except Exception as e:  # keep listening whatever happens
            text = ""
            print("transcribe error:", e, flush=True)
        if text:
            out.write(f"[{stamp}] {text}")


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


def mic_blocks(device, stop):
    import sounddevice as sd
    q = queue.Queue()

    def cb(indata, frames, t, status):
        q.put(indata[:, 0].copy())

    with sd.InputStream(samplerate=SR, channels=1, dtype="float32",
                        blocksize=int(SR * BLOCK), device=device, callback=cb):
        while not stop.is_set():
            try:
                yield q.get(timeout=0.5)
            except queue.Empty:
                pass


def file_blocks(path):
    import wave
    with wave.open(path) as w:
        audio = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
    n = int(SR * BLOCK)
    for i in range(0, len(audio), n):
        yield audio[i:i + n]


class Listener:
    """One listening period: microphone -> phrases -> transcript."""

    def __init__(self, device, jobs, out):
        self.device, self.jobs, self.out = device, jobs, out
        self.stop = threading.Event()
        self.thread = None

    def start(self, label=""):
        self.stop.clear()
        self.out.write(f"[{now()}] ===== START {datetime.date.today()} {label}".rstrip() + " =====")
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _run(self):
        try:
            chunker(mic_blocks(self.device, self.stop), self.jobs)
        except Exception as e:
            print("microphone error:", e, flush=True)

    def running(self):
        return self.thread is not None and self.thread.is_alive()

    def end(self):
        self.stop.set()
        if self.thread:
            self.thread.join(timeout=5)
        self.thread = None
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
    print("Transcript:", out.path, flush=True)

    from faster_whisper import WhisperModel
    if a.lang != "en" and a.model.endswith(".en"):
        a.model = a.model[:-3]
    print("Loading model", a.model, "...", flush=True)
    model = WhisperModel(a.model, device="cpu", compute_type="int8",
                         cpu_threads=os.cpu_count() or 4)
    jobs = queue.Queue()
    threading.Thread(target=worker, args=(model, a.lang, jobs, out), daemon=True).start()

    if a.file:
        out.write(f"[{now()}] ===== START {datetime.date.today()} test =====")
        chunker(file_blocks(a.file), jobs)
        jobs.put(None)
        time.sleep(0.2)
        while not jobs.empty():
            time.sleep(0.2)
        time.sleep(3)
        out.write(f"[{now()}] ===== STOP =====")
        return

    ear = Listener(a.device, jobs, out)
    if not a.standby:
        ear.start("manual")
        print("Listening. Press Ctrl+C to stop.", flush=True)
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            ear.end()
        return

    print("Standby. Waiting for the Live Follow page. Close this window to quit.", flush=True)
    last_beat = 0
    try:
        while True:
            want = os.path.exists(on_flag)
            if want and not ear.running():
                ear.start("live-follow")
            elif not want and ear.running():
                ear.end()
            if time.time() - last_beat >= BEAT:
                heartbeat(status, "listening" if ear.running() else "standby")
                last_beat = time.time()
            time.sleep(POLL)
    except KeyboardInterrupt:
        if ear.running():
            ear.end()
        heartbeat(status, "off")


if __name__ == "__main__":
    main()
