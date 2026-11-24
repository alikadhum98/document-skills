"""Tests for ear_logic.py. Run:  python -m unittest tools/live_ear/test_ear_logic.py
No microphone, browser or Whisper model is needed."""
import os, sys, tempfile, time, unittest
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ear_logic as L


class FlakyFile:
    """open() replacement that fails while `down` is true, like Drive during an outage."""

    def __init__(self):
        self.down, self.text = False, ""

    def __call__(self, path, mode, encoding=None):
        if self.down:
            raise OSError("drive offline")
        outer = self

        class F:
            def __enter__(s): return s
            def __exit__(s, *a): return False
            def write(s, t): outer.text += t
        return F()


class WriterTests(unittest.TestCase):
    def test_ten_minute_outage_loses_nothing(self):
        f = FlakyFile()
        w = L.Writer("x", opener=f)
        w.append("[10:00:00] before")
        f.down = True
        sent = [f"[10:{m:02d}:{s:02d}] line {m}-{s}" for m in range(1, 11) for s in (0, 30)]
        for line in sent:            # 20 lines over a simulated ten minutes, every flush fails
            self.assertFalse(w.append(line))
            self.assertFalse(w.flush())
        self.assertEqual(len(w.pending), 20)
        f.down = False
        self.assertTrue(w.flush())   # the background flusher's next attempt
        got = f.text.strip().splitlines()
        self.assertEqual(got, ["[10:00:00] before"] + sent)
        self.assertEqual(w.pending, [])


class RotateTests(unittest.TestCase):
    def setUp(self):
        import datetime
        self.dt = datetime
        self.d = tempfile.mkdtemp()
        self.path = os.path.join(self.d, "COP31_live.txt")
        self.arch = os.path.join(self.d, "COP31_live_archive")

    def write(self, text, days_ago=0):
        with open(self.path, "w", encoding="utf-8") as f:
            f.write(text)
        t = time.time() - days_ago * 86400
        os.utime(self.path, (t, t))

    def test_earlier_day_is_archived_and_file_emptied_in_place(self):
        self.write("[18:00:00] old line\n", days_ago=1)
        ino = os.stat(self.path).st_ino
        w = L.Writer(self.path)
        moved = w.rotate(self.arch)
        day = (self.dt.date.today() - self.dt.timedelta(days=1)).isoformat()
        self.assertTrue(moved.endswith(f"COP31_live_{day}.txt"))
        self.assertEqual(open(moved, encoding="utf-8").read(), "[18:00:00] old line\n")
        self.assertEqual(os.path.getsize(self.path), 0)
        self.assertEqual(os.stat(self.path).st_ino, ino)   # same file: Drive keeps its id
        w.append("[09:00:00] new day")
        self.assertEqual(open(self.path, encoding="utf-8").read(), "[09:00:00] new day\n")

    def test_same_day_small_file_stays(self):
        self.write("[09:00:00] today\n")
        self.assertIsNone(L.Writer(self.path).rotate(self.arch))
        self.assertFalse(os.path.exists(self.arch))

    def test_same_day_large_file_is_archived(self):
        self.write("x" * 400 + "\n")
        moved = L.Writer(self.path).rotate(self.arch, max_bytes=100)
        self.assertTrue(moved)
        self.assertEqual(os.path.getsize(self.path), 0)

    def test_missing_or_empty_file(self):
        self.assertIsNone(L.Writer(self.path).rotate(self.arch))
        self.write("", days_ago=2)
        self.assertIsNone(L.Writer(self.path).rotate(self.arch))


class AccurateTests(unittest.TestCase):
    def test_cuts_fall_in_the_silences(self):
        rate = 1000
        a = np.full(100 * rate, 0.3, np.float32)       # 100 s of speech
        for s in (25, 51, 77):                          # with short pauses here
            a[s * rate:(s + 1) * rate] = 0.0
        cuts = L.quiet_cuts(a, rate)
        self.assertEqual(len(cuts), 3)
        for c, s in zip(cuts, (25, 51, 77)):
            self.assertTrue(s * rate <= c <= (s + 1) * rate, (c, s))
        pieces = np.diff([0] + cuts + [len(a)])
        self.assertTrue(all(p <= 30 * rate for p in pieces))

    def test_pass_keeps_times_languages_and_speakers(self):
        with tempfile.TemporaryDirectory() as d:
            st = L.AudioStore(d, rate=1000)
            t0 = 1_800_000_000.0
            for i in range(60):
                st.write(np.full(1000, 0.0 if i in (27, 28) else 0.2, np.float32), end_time=t0 + i + 1)
            st.close()
            said = iter([("ar", [(1.0, "الكلمة الآن للمجموعة العربية")]),
                         ("en", [(2.0, "Thank you Chair, the Arab Group supports the phased approach.")]),
                         ("other", [])])
            lines = L.accurate_pass(st, t0, t0 + 60, lambda piece: next(said, ("other", [])), L.SpeakerTracker())
        self.assertEqual(len(lines), 2)
        self.assertTrue(lines[0].startswith(f"[{L.hms(t0 + 1)}] (دقيق) "))
        self.assertIn("[المتكلم: Arab Group]", lines[1])

    def test_speech_gaps(self):
        piece = np.full(25 * 16000, 0.2, np.float32)
        piece[20 * 16000:] = 0.0                      # the last five seconds are silence
        # covered 2 to 6 s: holes 0 to 2 (too short), 6 to 25 of which 20 to 25 is silent but joined
        self.assertEqual(L.speech_gaps(piece, [(2.0, 6.0)]), [(6.0, 25.0)])
        self.assertEqual(L.speech_gaps(piece, [(0.0, 20.0)]), [])          # only silence left
        self.assertEqual(L.speech_gaps(piece, []), [(0.0, 25.0)])

    def test_errors_are_reported_not_swallowed(self):
        with tempfile.TemporaryDirectory() as d:
            st = L.AudioStore(d, rate=1000)
            for i in range(40):
                st.write(np.full(1000, 0.2, np.float32), end_time=1_800_000_000.0 + i + 1)
            st.close()
            def broken(piece):
                raise RuntimeError("model file not found")
            errs = []
            self.assertEqual(L.accurate_pass(st, 1_800_000_000.0, 1_800_000_040.0, broken, errors=errs), [])
            self.assertEqual(errs[0], "RuntimeError: model file not found")
            errs = []
            L.accurate_pass(st, 1_900_000_000.0, 1_900_000_040.0, broken, errors=errs)
            self.assertEqual(errs[0], "no stored audio for this session")

    def test_block_is_written_together(self):
        f = FlakyFile()
        w = L.Writer("x", opener=f)
        f.down = True
        w.append("[10:00:00] live line")
        w.append_many(["A", "B", "C"])
        f.down = False
        w.flush()
        self.assertEqual(f.text.splitlines(), ["[10:00:00] live line", "A", "B", "C"])


class AudioTests(unittest.TestCase):
    def test_extract_across_segments_and_restart(self):
        with tempfile.TemporaryDirectory() as d:
            st = L.AudioStore(d, rate=1600, segment_secs=60)
            t0 = 1_800_000_000.0
            for i in range(150):     # 150 one-second blocks: crosses two segment boundaries
                st.write(np.full(1600, (i % 7) / 10, np.float32), end_time=t0 + i + 1)
            for i in range(10):      # the stream restarts 30 seconds later: a new segment
                st.write(np.full(1600, 0.5, np.float32), end_time=t0 + 180 + i + 1)
            st.close()
            self.assertEqual(len(st.segments()), 4)
            a = st.extract(t0 + 50, t0 + 70)
            self.assertEqual(len(a), 20 * 1600)
            self.assertAlmostEqual(float(a[0]), (50 % 7) / 10, places=3)
            self.assertAlmostEqual(float(a[-1]), (69 % 7) / 10, places=3)
            self.assertEqual(len(st.extract(t0 + 150, t0 + 180)), 0)   # nothing recorded then
            self.assertEqual(len(st.extract(t0 + 182, t0 + 185)), 3 * 1600)


class BackfillTests(unittest.TestCase):
    def test_gap_is_transcribed_with_original_times(self):
        with tempfile.TemporaryDirectory() as d:
            st = L.AudioStore(d, rate=1600, segment_secs=300)
            t0 = L.clock_to_ts("16:30:00", ref=L.clock_to_ts("23:00:00"))
            for i in range(900):     # fifteen minutes of audio
                st.write(np.full(1600, 0.1, np.float32), end_time=t0 + i + 1)
            calls = []

            def fake(audio):
                calls.append(len(audio))
                return [(2.0, "Thank you, Chair."), (12.5, "")]
            out = []
            b = L.Backfiller(st, fake, out.append, chunk_secs=60, sleep=lambda s: None, clock=lambda: t0 + 10_000)
            b.enqueue(t0 + 60, t0 + 660)   # a ten-minute network gap
            self.assertEqual(b.run_once(), 10)
            self.assertEqual(len(calls), 10)
            self.assertTrue(out[0].startswith("[16:31:00] ===== BACKFILL 600"))
            self.assertEqual(out[1], "[16:31:02] (تكملة) Thank you, Chair.")
            self.assertEqual(out[-2], "[16:40:02] (تكملة) Thank you, Chair.")
            self.assertIn("BACKFILL END 10", out[-1])
            self.assertIsNone(b.run_once())

    def test_which_gaps_need_backfill(self):
        self.assertTrue(L.needs_backfill("network no-speech stall", 314))
        self.assertTrue(L.needs_backfill("stall", 25))
        self.assertFalse(L.needs_backfill("silence", 300))
        self.assertFalse(L.needs_backfill("no-speech", 90))
        self.assertFalse(L.needs_backfill("network", 10))


class SpeakerTests(unittest.TestCase):
    def run_lines(self, lines):
        t = L.SpeakerTracker()
        return [t.feed(x) for x in lines]

    def test_cop31_cma18_snippet(self):
        # lines as the ear heard them on 19/11 (CMA 18), recognition errors included
        r = self.run_lines([
            "Thank you, Pete, and thank you for this proposal.",
            "Next on my list is LMS.",
            "Limitation Audible 6.2 but we also have the drive.",
            "Thank you. Next is United Arab Emirates please.",
            "United Arab Emirates aligns with the statement delivered by the Arab Group.",
            "approaches 3 and 4 remain bracketed.",
            "Russia, please.",
            "we can move forward with this. Thank you.",
        ])
        self.assertEqual([x[0] for x in r], [None, "Chair", "LMDC", "Chair", "Arab Group (UAE)", "Arab Group (UAE)", "Chair", "Russian Federation"])
        self.assertEqual([x[1] for x in r], [None, "lmdc", None, None, "arab_group", None, None, None])

    def test_alert_once_per_turn(self):
        t = L.SpeakerTracker()
        self.assertEqual(t.feed("The floor goes to the LMDC.")[1], "lmdc")
        self.assertIsNone(t.feed("We have strict concerns about paragraph 21.")[1])
        self.assertIsNone(t.feed("EU, you have the floor.")[1])
        self.assertEqual(t.feed("Next is the Like-Minded Developing Countries.")[1], "lmdc")

    def test_arabic_coordination_meeting(self):
        # Arabic as Edge (ar-IQ) writes it, with Iraqi speech and spelling variants
        r = self.run_lines([
            "شكرا جزيلا، هسه الكلمة للمملكة العربية السعودية تفضلوا",
            "شكرا سيادة الرئيس، نتحدث باسم المجموعة العربية",
            "نرفض أي إرشادات جديدة قبل المراجعة",
            "شكرا، الكلمة الآن لمصر",
            "مصر تؤيد ما قالته المجموعة",
            "ننتقل الى الدول النامية المتشابهة التفكير",
            "نحن لا نقبل هذه الفقرة",
            "العراق تفضل",
        ])
        self.assertEqual([x[0] for x in r], ["Chair", "Arab Group (Saudi Arabia)", "Arab Group (Saudi Arabia)", "Chair", "Egypt", "Chair", "LMDC", "Chair"])
        self.assertEqual([x[1] for x in r], [None, "arab_group", None, None, None, "lmdc", None, None])

    def test_arabic_words_do_not_trigger(self):
        r = self.run_lines(["نحتاج لمصر ولكل الدول دعما اكبر", "لكن الفقرة غير مقبولة"])
        self.assertEqual([x[0] for x in r], [None, None])

    def test_cue_without_article_from_the_pc_test(self):
        # the accurate pass of 24/11 wrote the cue without its article, joined to the speech that followed
        t = L.SpeakerTracker()
        t.tag("Thank you. Next on my list is the European Union")
        line, _ = t.tag("كلمة الان للعراق. نحن الان في هذا الاجتماع نسلم بيانات الجرد قبل 31 آذار")
        self.assertTrue(line.startswith("[المتكلم: Chair]"))
        self.assertEqual(t.tag("ولقد انجزنا البلاغ الوطني الثاني")[0][:15], "[المتكلم: Iraq]")

    def test_chair_thanks_the_last_speaker(self):
        # the accurate pass of 24/11 left the chair's closing words under Iraq
        t = L.SpeakerTracker()
        t.tag("كلمة الان للعراق.")
        self.assertEqual(t.tag("احنا نريد الجرد يخلص")[0][:15], "[المتكلم: Iraq]")
        self.assertEqual(t.tag("Thank you Eric, I see no other request for the floor")[0][:16], "[المتكلم: Chair]")
        self.assertEqual(t.tag("We will meet again on Monday at 10 o'clock")[0][:16], "[المتكلم: Chair]")
        t2 = L.SpeakerTracker()
        t2.tag("Next on my list is Iraq.")
        # a delegate thanking the chair stays the delegate (and its alignment is kept)
        self.assertTrue(t2.tag("Thank you, Chair. Iraq aligns itself with the Arab Group")[0].startswith("[المتكلم: Arab Group (Iraq)]"))

    def test_garbled_group_names(self):
        t = L.SpeakerTracker()
        self.assertEqual(t.name_at_start("out space"), "AOSIS")
        self.assertEqual(t.name_at_start("CFRM."), "CfRN")
        self.assertEqual(t.name_at_start("ILAC proposal"), "AILAC")
        self.assertEqual(t.name_at_start("united arab emirates"), "UAE")
        self.assertEqual(t.name_at_start("the Arab Group"), "Arab Group")
        self.assertIsNone(t.name_at_start("this paragraph"))

    def test_tag_prefix(self):
        t = L.SpeakerTracker()
        t.tag("Next is Japan.")
        self.assertEqual(t.tag("Thank you, co-facilitators.")[0], "[المتكلم: Japan] Thank you, co-facilitators.")


class LanguageTests(unittest.TestCase):
    """A room that starts in English, turns to Arabic, has a short English quotation, then silence."""

    def make(self, script):
        d = tempfile.mkdtemp()
        st = L.AudioStore(d, rate=1600, segment_secs=60)
        t0 = 1_800_000_000.0
        lang_at = {}
        for i, (lang, loud) in enumerate(script):     # one entry per second of room audio
            st.write(np.full(1600, loud, np.float32), end_time=t0 + i + 1)
            lang_at[i] = lang
        clock = {"t": t0}

        def detect(audio):  # what Whisper would say about the last seconds: the language heard last
            sec = int(clock["t"] - t0) - 1
            return lang_at[sec], 0.95
        w = L.LanguageWatcher(st, detect, window=8, clock=lambda: clock["t"])
        return w, clock, t0

    def run_steps(self, w, clock, t0, until, every=10):
        out = []
        for t in range(every, until + 1, every):
            clock["t"] = t0 + t
            r = w.step()
            if r:
                out.append((t, r[0], int(r[1] - t0)))
        return out

    def test_switches_and_ignores_short_quotation(self):
        script = [("en", .1)] * 40 + [("ar", .1)] * 60 + [("en", .1)] * 12 + [("ar", .1)] * 38 + [("ar", 0)] * 30
        w, clock, t0 = self.make(script)
        got = self.run_steps(w, clock, t0, 180)
        # English confirmed first, Arabic adopted after two readings (40 and 50 s, switch from 42 s),
        # the 12-second English quotation (100 to 111 s) is heard once only and ignored, silence ignored
        self.assertEqual(got, [(60, "ar", 42)])
        self.assertEqual(w.current, "ar")

    def test_first_decision_is_quick(self):
        w, clock, t0 = self.make([("ar", .1)] * 30)
        self.assertEqual(self.run_steps(w, clock, t0, 30), [(10, "ar", 2)])

    def test_other_languages_and_silence_are_ignored(self):
        w, clock, t0 = self.make([("fr", .1)] * 30 + [("ar", 0)] * 30)
        self.assertEqual(self.run_steps(w, clock, t0, 60), [])
        self.assertEqual(w.current, "en")

    def test_two_way_reading(self):
        # what the PC heard on 20/11: accented English read only 0.27 English with Arabic far behind
        self.assertEqual(L.two_way({"en": 0.27, "ar": 0.04, "nn": 0.1})[0], "en")
        self.assertGreater(L.two_way({"en": 0.27, "ar": 0.04})[1], 0.85)
        self.assertEqual(L.two_way({"nn": 0.27, "en": 0.05, "ar": 0.04}), ("other", 0.0))
        self.assertEqual(L.two_way({"ar": 0.6, "en": 0.2})[0], "ar")

    def test_backfill_uses_the_job_language(self):
        seen = []
        with tempfile.TemporaryDirectory() as d:
            st = L.AudioStore(d, rate=1600)
            for i in range(20):
                st.write(np.full(1600, .1, np.float32), end_time=1_800_000_000.0 + i + 1)
            st.close()
            b = L.Backfiller(st, lambda a, lang=None: seen.append(lang) or [(0, "x")], lambda line: None,
                             sleep=lambda s: None, clock=lambda: 1_900_000_000.0)
            b.enqueue(1_800_000_000.0, 1_800_000_010.0, "ar")
            b.enqueue(1_800_000_010.0, 1_800_000_020.0)
            b.run_once()
            b.run_once()
        self.assertEqual(seen, ["ar", None])


if __name__ == "__main__":
    unittest.main()
