"""Live ear: listens to the room microphone and writes a timestamped
English transcript to a text file (synced to Google Drive) every few seconds.

Usage (Windows):
    python live_ear.py --out "G:\\My Drive\\COP31\\live\\live.txt"
Options:
    --model base.en|small.en   accuracy versus speed (default small.en)
    --lang en|ar|auto          spoken language (default en)
    --device N                 microphone number from --list
    --list                     list audio input devices and exit
    --file clip.wav            transcribe a 16 kHz mono wav instead of the microphone (test)
"""
import argparse, os, queue, sys, threading, time, datetime
import numpy as np

SR = 16000
BLOCK = 0.1            # seconds per audio block
SILENCE_END = 0.7      # seconds of silence that closes a phrase
MIN_PHRASE = 2.0       # seconds
MAX_PHRASE = 12.0      # seconds


def now():
    return datetime.datetime.now().strftime("%H:%M:%S")


def writer(path):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    def write(line):
        with open(path, "a", encoding="utf-8") as f:
            f.write(line + "\n")
            f.flush()
            os.fsync(f.fileno())
        print(line, flush=True)
    return write


def worker(model, lang, jobs, write):
    while True:
        item = jobs.get()
        if item is None:
            return
        stamp, audio = item
        segs, _ = model.transcribe(audio, language=None if lang == "auto" else lang,
                                   beam_size=1, vad_filter=True,
                                   condition_on_previous_text=False)
        text = " ".join(s.text.strip() for s in segs).strip()
        if text:
            write(f"[{stamp}] {text}")


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
    if buf:
        jobs.put((start or now(), np.concatenate(buf)))


def mic_blocks(device):
    import sounddevice as sd
    q = queue.Queue()
    def cb(indata, frames, t, status):
        q.put(indata[:, 0].copy())
    with sd.InputStream(samplerate=SR, channels=1, dtype="float32",
                        blocksize=int(SR * BLOCK), device=device, callback=cb):
        while True:
            yield q.get()


def file_blocks(path):
    import wave  # 16 kHz mono 16-bit wav
    with wave.open(path) as w:
        audio = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
    n = int(SR * BLOCK)
    for i in range(0, len(audio), n):
        yield audio[i:i + n]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(os.path.expanduser("~"), "live.txt"))
    ap.add_argument("--model", default="small.en")
    ap.add_argument("--lang", default="en")
    ap.add_argument("--device", type=int, default=None)
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--file")
    a = ap.parse_args()
    if a.list:
        import sounddevice as sd
        print(sd.query_devices())
        return
    from faster_whisper import WhisperModel
    if a.lang != "en" and a.model.endswith(".en"):
        a.model = a.model[:-3]
    print("Loading model", a.model, "...", flush=True)
    model = WhisperModel(a.model, device="cpu", compute_type="int8")
    write = writer(a.out)
    write(f"[{now()}] ===== START {datetime.date.today()} =====")
    jobs = queue.Queue()
    t = threading.Thread(target=worker, args=(model, a.lang, jobs, write), daemon=True)
    t.start()
    print("Listening. Press Ctrl+C to stop.", flush=True)
    try:
        chunker(file_blocks(a.file) if a.file else mic_blocks(a.device), jobs)
    except KeyboardInterrupt:
        pass
    jobs.put(None)
    t.join()
    write(f"[{now()}] ===== STOP =====")


if __name__ == "__main__":
    main()
