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
