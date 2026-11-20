"""Live Ear (PC): logic that does not depend on Windows, the browser or the microphone.

1. Writer: every line goes to the Drive transcript through a pending queue that a
   background flusher retries, so a Drive or network outage delays lines but never
   drops them.
2. AudioStore: the room audio is kept on the PC in five-minute WAV segments while a
   session runs, so any stretch the browser recogniser missed can be transcribed later.
3. Backfiller: when the browser reports a gap caused by the network or a stall, the
   missing stretch is cut from the stored audio and transcribed offline. Its lines carry
   the original times and the mark (تكملة).
4. LanguageWatcher: in automatic language mode, checks the last seconds of stored audio
   and tells the window to switch the recogniser between English and Arabic. The
   stretch spoken before the switch is recovered from the stored audio.
5. SpeakerTracker: reads the chair's cues ("next on my list is the LMDC", "UK, please",
   "on behalf of the Arab Group") and tags each line with the current speaker. It raises
   an alert when the Arab Group or the LMDC take the floor.

Standard library and numpy only. Tested by test_ear_logic.py.
"""
import datetime, json, os, queue, re, threading, time, wave

# ---------------------------------------------------------------- writer

class Writer:
    """Appends lines to a file that may be briefly unavailable (Google Drive)."""

    def __init__(self, path, opener=open, clock=time.time):
        self.path, self.opener, self.clock = path, opener, clock
        self.lock = threading.Lock()
        self.pending = []
        self.failing_since = 0.0

    def append(self, line):
        with self.lock:
            self.pending.append(line)
        return self.flush()

    def flush(self):
        with self.lock:
            if not self.pending:
                return True
            try:
                with self.opener(self.path, "a", encoding="utf-8") as f:
                    f.write("\n".join(self.pending) + "\n")
                self.pending.clear()
                self.failing_since = 0.0
                return True
            except OSError:
                if not self.failing_since:
                    self.failing_since = self.clock()
                return False

    def run_flusher(self, every=5.0, stop=None):
        def loop():
            while not (stop and stop.is_set()):
                time.sleep(every)
                self.flush()
        t = threading.Thread(target=loop, daemon=True)
        t.start()
        return t

# ---------------------------------------------------------------- audio store

STAMP = "%Y%m%d_%H%M%S"


class AudioStore:
    """Rolling WAV segments of 16-bit mono audio, named by their start time."""

    def __init__(self, folder, rate=16000, segment_secs=300, keep_hours=8):
        self.folder, self.rate = folder, rate
        self.segment_secs, self.keep_hours = segment_secs, keep_hours
        self.lock = threading.Lock()
        self.cur = None          # open wave writer
        self.cur_start = 0.0     # wall time of the first sample in the current segment
        self.cur_samples = 0
        os.makedirs(folder, exist_ok=True)

    def _open(self, start):
        self.close()
        name = "audio_" + datetime.datetime.fromtimestamp(start).strftime(STAMP) + "_%03d.wav" % int((start % 1) * 1000)
        w = wave.open(os.path.join(self.folder, name), "wb")
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(self.rate)
        self.cur, self.cur_start, self.cur_samples = w, start, 0

    def write(self, block, end_time=None):
        """block: float32 numpy array in [-1, 1]; end_time: wall time of its last sample."""
        import numpy as np
        end_time = time.time() if end_time is None else end_time
        start = end_time - len(block) / self.rate
        with self.lock:
            expected = self.cur_start + self.cur_samples / self.rate if self.cur else None
            # a new segment when none is open, when it is full, or when the stream jumped (restart)
            if self.cur is None or self.cur_samples >= self.segment_secs * self.rate or abs(start - expected) > 1.0:
                self._open(start)
            pcm = (np.clip(block, -1, 1) * 32767).astype("<i2").tobytes()
            self.cur.writeframes(pcm)
            self.cur_samples += len(block)

    def close(self):
        if self.cur is not None:
            try:
                self.cur.close()
            except Exception:
                pass
            self.cur = None

    def segments(self):
        out = []
        for fn in sorted(os.listdir(self.folder)):
            m = re.fullmatch(r"audio_(\d{8}_\d{6})_(\d{3})\.wav", fn)
            if m:
                t = datetime.datetime.strptime(m.group(1), STAMP).timestamp() + int(m.group(2)) / 1000
                out.append((t, os.path.join(self.folder, fn)))
        return out

    def extract(self, start, end):
        """Audio between two wall times, joined across segments (float32 numpy array)."""
        import numpy as np
        with self.lock:
            if self.cur is not None:
                self.cur._file.flush()
            parts = []
            for t0, path in self.segments():
                try:
                    with wave.open(path, "rb") as w:
                        n = w.getnframes()
                        t1 = t0 + n / self.rate
                        if t1 <= start or t0 >= end:
                            continue
                        a = int(max(0, (start - t0) * self.rate))
                        b = int(min(n, (end - t0) * self.rate))
                        w.setpos(a)
                        raw = w.readframes(b - a)
                except (wave.Error, EOFError, OSError):
                    continue
                parts.append(np.frombuffer(raw, "<i2").astype(np.float32) / 32768)
        return np.concatenate(parts) if parts else np.zeros(0, np.float32)

    def prune(self, now=None):
        now = time.time() if now is None else now
        for t0, path in self.segments():
            if now - t0 > self.keep_hours * 3600 and (self.cur is None or t0 != self.cur_start):
                try:
                    os.remove(path)
                except OSError:
                    pass

# ---------------------------------------------------------------- backfill

BACKFILL_REASONS = ("network", "stall", "start-failed", "browser")


def needs_backfill(why, secs, min_secs=20):
    """Gaps of real silence need nothing; gaps where recognition failed are filled from audio."""
    return secs >= min_secs and any(r in (why or "") for r in BACKFILL_REASONS)


def clock_to_ts(hms, ref=None):
    """'14:05:09' today (or yesterday when that would be in the future) as a timestamp."""
    ref = time.time() if ref is None else ref
    d = datetime.datetime.fromtimestamp(ref)
    h, m, s = (int(x) for x in hms.split(":"))
    t = d.replace(hour=h, minute=m, second=s, microsecond=0).timestamp()
    return t - 86400 if t > ref + 60 else t


def hms(ts):
    return datetime.datetime.fromtimestamp(ts).strftime("%H:%M:%S")


class Backfiller:
    """Transcribes stored audio for gaps the browser missed, one gap at a time."""

    def __init__(self, store, transcribe, write, chunk_secs=30, settle=3.0, sleep=time.sleep, clock=time.time):
        self.store, self.transcribe, self.write = store, transcribe, write
        self.chunk_secs, self.settle, self.sleep, self.clock = chunk_secs, settle, sleep, clock
        self.jobs = queue.Queue()

    def enqueue(self, start, end, lang=None):
        """lang: "en" or "ar" to force the backfill language (after a language switch)."""
        self.jobs.put((start, end, lang))

    def run_once(self):
        """Process one queued gap. Returns the number of lines written (None when idle)."""
        try:
            job = self.jobs.get_nowait()
            start, end, lang = (job + (None,))[:3]
        except queue.Empty:
            return None
        wait = end + self.settle - self.clock()
        if wait > 0:
            self.sleep(wait)
        audio = self.store.extract(start, end)
        rate = self.store.rate
        if not len(audio):
            self.write(f"[{hms(start)}] ===== BACKFILL no audio for {int(end - start)} ثانية =====")
            return 0
        self.write(f"[{hms(start)}] ===== BACKFILL {int(end - start)} ثانية =====")
        n = 0
        step = int(self.chunk_secs * rate)
        for i in range(0, len(audio), step):
            piece = audio[i:i + step]
            try:
                segs = (self.transcribe(piece, lang) if lang else self.transcribe(piece)) or []
            except Exception as e:  # keep going whatever happens
                self.write(f"[{hms(start + i / rate)}] ===== BACKFILL error: {str(e)[:80]} =====")
                continue
            for off, text in segs:
                text = " ".join(str(text).split())
                if text:
                    self.write(f"[{hms(start + i / rate + off)}] (تكملة) {text}")
                    n += 1
        self.write(f"[{hms(end)}] ===== BACKFILL END {n} سطر =====")
        return n

    def run_forever(self, stop=None):
        def loop():
            while not (stop and stop.is_set()):
                if self.run_once() is None:
                    time.sleep(1.0)
        t = threading.Thread(target=loop, daemon=True)
        t.start()
        return t


def whisper_transcriber(model_name="small.en", threads=2, language="en"):
    """A transcribe(audio) -> [(offset_seconds, text)] backed by faster-whisper, or None.
    Arabic needs a multilingual model (small, not small.en)."""
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        return None
    holder = {}

    def run(audio):
        if "m" not in holder:
            holder["m"] = WhisperModel(model_name, device="cpu", compute_type="int8", cpu_threads=threads)
        segs, _ = holder["m"].transcribe(audio, language=language, beam_size=1, vad_filter=True,
                                          condition_on_previous_text=False)
        return [(s.start, s.text) for s in segs if s.avg_logprob > -1.5 and s.compression_ratio < 2.4]
    return run


def language_transcriber(session_lang, threads=2):
    """Backfill model chosen by the session language: small.en for English, small for Arabic."""
    en = whisper_transcriber("small.en", threads, "en")
    if en is None:
        return None
    ar = whisper_transcriber("small", threads, "ar")

    def run(audio, lang=None):
        lang = lang or session_lang()
        return (ar if str(lang).startswith("ar") else en)(audio)
    return run

# ---------------------------------------------------------------- automatic language

AUTO_LANGS = {"en": "en-US", "ar": "ar-IQ"}  # recogniser used for each detected language


def whisper_language_detector(model_name="base", threads=1):
    """A detect(audio) -> (language, probability) backed by faster-whisper, or None.
    Only the language is computed: the transcript is never decoded."""
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        return None
    holder = {}

    def run(audio):
        if "m" not in holder:
            holder["m"] = WhisperModel(model_name, device="cpu", compute_type="int8", cpu_threads=threads)
        _, info = holder["m"].transcribe(audio, beam_size=1, vad_filter=False)
        return info.language, float(info.language_probability)
    return run


class LanguageWatcher:
    """Decides, from the room audio itself, whether the recogniser should run in English or Arabic.

    step() looks at the last `window` seconds once. The first decision of a session is quick
    (one confident reading). Later switches need `need` readings in a row, so one English
    quotation inside an Arabic meeting does not flip the recogniser back and forth.
    Other languages and silence are ignored."""

    def __init__(self, store, detect, window=8.0, quick_prob=0.8, prob=0.6, need=2, min_rms=0.004, clock=time.time):
        self.store, self.detect, self.window = store, detect, window
        self.quick_prob, self.prob, self.need, self.min_rms, self.clock = quick_prob, prob, need, min_rms, clock
        self.reset("en")

    def reset(self, start_lang="en"):
        self.current = start_lang
        self.decided = False
        self.streak = [None, 0, 0.0]  # language, readings in a row, start of the first reading

    def step(self):
        """Returns (language, since) when the recogniser should switch, otherwise None."""
        import numpy as np
        end = self.clock()
        start = end - self.window
        audio = self.store.extract(start, end)
        if len(audio) < self.window * self.store.rate * 0.6:
            return None
        if float(np.sqrt(np.mean(np.square(audio)))) < self.min_rms:
            return None  # silence tells nothing
        lang, p = self.detect(audio)
        if lang not in AUTO_LANGS:
            self.streak = [None, 0, 0.0]
            return None
        if lang == self.current:
            if p >= self.prob:
                self.decided = True
            self.streak = [None, 0, 0.0]
            return None
        if self.streak[0] == lang:
            self.streak[1] += 1
        else:
            self.streak = [lang, 1, start]
        quick = not self.decided and p >= self.quick_prob
        if quick or (p >= self.prob and self.streak[1] >= self.need):
            since = self.streak[2]
            self.current, self.decided = lang, True
            self.streak = [None, 0, 0.0]
            return lang, since
        return None

# ---------------------------------------------------------------- speakers

# canonical name -> spoken forms, including recognition errors heard at COP31
ALIASES = {
    "Arab Group": [r"arab group", r"group of arab states", r"error\.? group"],
    "LMDC": [r"l\.? ?m\.? ?d\.? ?c", r"like[- ]minded(?: developing countries| group)?", r"lmcc", r"lmpc", r"lmc", r"lms", r"lbc", r"lntc", r"lnmdc"],
    "AOSIS": [r"aosis", r"a\.? ?o\.? ?s\.? ?i\.? ?s", r"alliance of small island states", r"out ?space", r"out ?sis"],
    "AILAC": [r"ailac", r"i ?lac", r"independent alliance of latin america"],
    "LDC Group": [r"least developed countries", r"ldcs?(?: group)?"],
    "African Group": [r"african group(?: of negotiators)?", r"agn"],
    "G77 and China": [r"g ?77(?: and china)?", r"group of 77(?: and china)?"],
    "CfRN": [r"coalition for rainforest nations", r"cfr[nm]"],
    "EIG": [r"environmental integrity group", r"eig"],
    "EU": [r"european union", r"the eu", r"eu"],
    "UK": [r"united kingdom", r"the uk", r"uk", r"britain"],
    "UAE": [r"united arab emirates", r"the emirates", r"emirates", r"uae"],
    "Saudi Arabia": [r"kingdom of saudi arabia", r"saudi arabia", r"saudi"],
    "Russian Federation": [r"russian federation", r"russia", r"russian"],
    "Republic of Korea": [r"republic of korea", r"korea"],
    "Japan": [r"japan"], "China": [r"china"], "Brazil": [r"brazil"], "Egypt": [r"egypt"],
    "Switzerland": [r"switzerland"], "Norway": [r"norway"], "Australia": [r"australia"],
    "Canada": [r"canada"], "India": [r"india"], "Pakistan": [r"pakistan"], "Iraq": [r"iraq"],
    "Iran": [r"iran"], "Bolivia": [r"bolivia"], "Singapore": [r"singapore"], "Germany": [r"germany"],
    "New Zealand": [r"new zealand"], "United States": [r"united states", r"the us", r"usa"],
    "Secretariat": [r"(?:the )?secretariat", r"الامانه"],
}
# Arabic names, written after norm_ar: alef forms become ا, ة becomes ه, ى becomes ي
ALIASES_AR = {
    "Arab Group": [r"المجموعه العربيه", r"مجموعه الدول العربيه", r"المجموعه العربي"],
    "LMDC": [r"(?:مجموعه )?الدول الناميه المتشابهه(?: التفكير)?", r"(?:الدول )?المتشابهه التفكير", r"المتشابهين"],
    "G77 and China": [r"مجموعه ال ?77(?: والصين)?", r"مجموعه السبعه والسبعين(?: والصين)?"],
    "African Group": [r"المجموعه الافريقيه"],
    "LDC Group": [r"(?:مجموعه )?اقل البلدان نموا"],
    "EU": [r"الاتحاد الاوروبي"],
    "Iraq": [r"(?:جمهوريه )?العراق", r"الوفد العراقي"],
    "Saudi Arabia": [r"(?:المملكه العربيه )?السعوديه"],
    "UAE": [r"الامارات(?: العربيه المتحده)?"],
    "Egypt": [r"مصر"], "Jordan": [r"الاردن"], "Kuwait": [r"الكويت"], "Qatar": [r"قطر"],
    "Oman": [r"(?:سلطنه )?عمان"], "Bahrain": [r"البحرين"], "Algeria": [r"الجزائر"],
    "Morocco": [r"المغرب"], "Tunisia": [r"تونس"], "Lebanon": [r"لبنان"], "Sudan": [r"السودان"],
    "Libya": [r"ليبيا"], "Palestine": [r"فلسطين"], "Syria": [r"سوريا"], "Yemen": [r"اليمن"],
    "China": [r"الصين"], "Iran": [r"ايران"], "Chair": [r"(?:رئيس الجلسه|الرئيس)"],
}
for _k, _v in ALIASES_AR.items():
    ALIASES[_k] = ALIASES.get(_k, []) + _v


def norm_ar(s):
    """One spelling for letters that Arabic speech recognition writes in several ways."""
    s = re.sub("[ً-ْـ]", "", s)  # diacritics and tatweel
    return s.translate(str.maketrans("أإآٱةى", "ااااهي"))


ALERT_FOR = {"Arab Group": "arab_group", "LMDC": "lmdc"}
GROUPS = {"Arab Group", "LMDC", "AOSIS", "AILAC", "LDC Group", "African Group", "G77 and China", "CfRN", "EIG", "EU"}

CUE_BEFORE = [  # the name comes after the cue
    r"next (?:on (?:my|the) list )?(?:is|we have|speaker is|i have|turn to)",
    r"(?:i |we )?(?:now )?(?:give|turn|pass|hand) (?:the floor )?(?:over )?(?:now )?to",
    r"(?:we'll|we will|let's|let me|i'll|i will) (?:now )?(?:go|turn|move) (?:next )?(?:over )?to",
    r"followed by",
    r"i (?:now )?(?:see|have) (?:a flag (?:from|by) )",
    r"(?:the )?floor (?:goes|now goes) to",
    # Arabic, including Iraqi speech (هسه = now), after norm_ar
    r"(?:اعطي |نعطي )?ب?(?:الكلمه|الدور) (?:الان |هسه |هسا )?(?:الي ?|ل)",
    r"(?:ننتقل|نمر) (?:الان |هسه |هسا )?(?:الي ?|ل)",
    r"(?:المتحدث|المتكلم) (?:التالي|القادم)(?: هو| هي)?",
    r"(?:اعطي|نعطي) الكلمه(?: الان| هسه)?(?: الي)?",
]
CUE_AFTER = r"(?:,|\.|،)?\s*(?:please|you have the floor|the floor is yours|over to you|go ahead|تفضل|تفضلي|تفضلوا|الكلمه لكم|الكلمه لك)(?![\w])"
BEHALF = r"(?:on behalf of|speaking for|aligns? (?:itself |ourselves |myself )?with(?: the statement (?:delivered |made )?by)?|associates? (?:itself )?with|باسم|نيابه عن|بالنيابه عن)"


def load_aliases(path=None):
    al = {k: list(v) for k, v in ALIASES.items()}
    if path and os.path.isfile(path):
        try:
            with open(path, encoding="utf-8") as f:
                for k, v in json.load(f).items():
                    al.setdefault(k, [])
                    al[k] = list(v) + al[k]
        except (OSError, ValueError):
            pass
    return al


class SpeakerTracker:
    def __init__(self, aliases=None):
        al = aliases or ALIASES
        pairs = [(c, v) for c, vs in al.items() for v in vs]
        pairs.sort(key=lambda p: -len(p[1]))  # longest spoken form first (united arab emirates before arab)
        self.names = [(c, re.compile(r"(?<![\w])(?:the )?" + norm_ar(v) + r"(?![\w])", re.I)) for c, v in pairs]
        self.before = [re.compile(r"(?<![\w])" + c + r"\s*(?:the\s+)?(?P<x>.{1,60})", re.I) for c in CUE_BEFORE]
        self.after = re.compile(r"(?P<x>[\w .'-]{2,45}?)" + CUE_AFTER, re.I)
        self.behalf = re.compile(r"(?<![\w])" + BEHALF + r"\s+(?:the\s+)?(?P<x>.{1,60})", re.I)
        self.speaker = None
        self.alerted = None

    def name_at_start(self, s):
        s = norm_ar(s).strip(" ,.:;،")
        tries = [s]
        if s.startswith("ل"):  # Arabic (ل) joined to the name: لمصر, للعراق, للمجموعه
            tries += [s[1:], "ا" + s[1:]]
        for t in tries:
            for canon, rx in self.names:
                if canon != "Chair" and rx.match(t):
                    return canon
        return None

    def name_at_end(self, s):
        s = norm_ar(s).strip(" ,.:;،")
        best = None
        for canon, rx in self.names:
            if canon == "Chair":
                continue
            for m in rx.finditer(s):
                if m.end() >= len(s) - 1 and (best is None or m.start() < best[1]):
                    best = (canon, m.start())
        return best[0] if best else None

    def feed(self, text):
        """Returns (speaker_for_this_line, alert) and updates the speaker for the next lines."""
        text = norm_ar(text)
        line_speaker, nxt = self.speaker, None
        for rx in self.before:
            for m in rx.finditer(text):
                who = self.name_at_start(m.group("x"))
                if who:
                    nxt = who
        if nxt is None:
            for m in self.after.finditer(text):
                who = self.name_at_end(m.group("x"))
                if who:
                    nxt = who
        if nxt is not None:
            line_speaker = "Chair"  # the line that calls the next speaker is the chair's
            self.speaker = nxt
        b = self.behalf.search(text)
        if b:
            grp = self.name_at_start(b.group("x"))
            if grp in GROUPS and grp != self.speaker:
                own = self.speaker if (self.speaker and self.speaker not in GROUPS and self.speaker != "Chair") else None
                self.speaker = grp + (f" ({own})" if own else "")
                line_speaker = self.speaker
        alert = None
        base = (self.speaker or "").split(" (")[0]
        if base in ALERT_FOR and self.alerted != self.speaker:
            alert = ALERT_FOR[base]
            self.alerted = self.speaker
        elif base not in ALERT_FOR:
            self.alerted = None
        return line_speaker, alert

    def tag(self, text):
        who, alert = self.feed(text)
        return (f"[المتكلم: {who}] {text}" if who else text), alert
