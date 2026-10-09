"""Tests: python -m unittest discover tests

Unit tests are self-contained. The integration test synthesises speech with the Windows voices (SAPI)
and runs the real model; it is skipped where SAPI or the model is unavailable.
"""
import os
import subprocess
import sys
import tempfile
import unittest
import warnings
import wave
from pathlib import Path

import numpy as np

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hangazonosito import audio, engine
from hangazonosito.i18n import STRINGS, tr


def write_wav(path: str, samples: np.ndarray, rate: int = 16_000) -> None:
    with wave.open(path, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes((np.clip(samples, -1, 1) * 32767).astype("<i2").tobytes())


def tone(seconds: float, rate: int = 16_000, freq: float = 220.0, amp: float = 0.5) -> np.ndarray:
    t = np.arange(int(seconds * rate)) / rate
    return (amp * np.sin(2 * np.pi * freq * t)).astype(np.float32)


class AudioTests(unittest.TestCase):
    def test_trim_removes_long_silence(self):
        quiet = np.zeros(16_000 * 3, dtype=np.float32) + 1e-5
        samples = np.concatenate([quiet, tone(2.0), quiet])
        trimmed = audio.trim_silence(samples)
        self.assertLess(len(trimmed), len(samples) * 0.5)
        self.assertGreater(len(trimmed) / 16_000, 1.9)

    def test_trim_keeps_audio_when_there_is_no_speech(self):
        silent = np.zeros(16_000 * 2, dtype=np.float32) + 1e-6
        self.assertEqual(len(audio.trim_silence(silent)), len(silent))

    def test_segments_short_audio_is_one_window(self):
        self.assertEqual(len(audio.segments(tone(4.0))), 1)

    def test_segments_cover_the_whole_recording(self):
        samples = tone(20.0)
        parts = audio.segments(samples)
        self.assertGreaterEqual(len(parts), 5)
        self.assertTrue(all(len(p) == 6 * 16_000 for p in parts))
        self.assertTrue(np.array_equal(parts[-1], samples[-6 * 16_000:]))   # last window reaches the end

    def test_load_wav_resamples_to_16k_mono(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "a.wav")
            write_wav(path, tone(1.0, rate=44_100), rate=44_100)
            samples = audio.load_audio(path)
            self.assertEqual(samples.dtype, np.float32)
            self.assertAlmostEqual(len(samples) / 16_000, 1.0, delta=0.01)

    def test_missing_and_empty_files(self):
        with self.assertRaises(audio.AudioError) as missing:
            audio.load_audio("does-not-exist.wav")
        self.assertEqual(missing.exception.key, "err_missing")
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "empty.wav")
            write_wav(path, np.zeros(0, dtype=np.float32))
            with self.assertRaises(audio.AudioError):
                audio.load_audio(path)


class EngineTests(unittest.TestCase):
    def test_confidence_is_50_at_threshold_and_monotonic(self):
        self.assertAlmostEqual(engine.confidence(engine.THRESHOLD), 50.0)
        self.assertLess(engine.confidence(0.0), engine.confidence(0.25))
        self.assertLess(engine.confidence(0.25), engine.confidence(0.7))
        self.assertGreater(engine.confidence(0.7), 95)

    def test_verdict_zones(self):
        self.assertEqual(engine.verdict_for(0.6), "same")
        self.assertEqual(engine.verdict_for(0.1), "different")
        self.assertEqual(engine.verdict_for(0.25), "uncertain")
        self.assertEqual(engine.verdict_for(0.29), "uncertain")


class TextTests(unittest.TestCase):
    def test_languages_have_the_same_keys(self):
        self.assertEqual(set(STRINGS["hu"]), set(STRINGS["en"]))

    def test_strings_format(self):
        sample = dict(a="x", y=1, n=1, s=1, d=1)
        for table in STRINGS.values():
            for value in table.values():
                value.format(**sample)

    def test_fallback_language(self):
        self.assertEqual(tr("xx", "clear"), "Clear")


def sapi_voices() -> list:
    """Names of installed Windows speech voices (empty where SAPI is unavailable)."""
    script = ("Add-Type -AssemblyName System.Speech;"
              "(New-Object System.Speech.Synthesis.SpeechSynthesizer).GetInstalledVoices() "
              "| ForEach-Object { $_.VoiceInfo.Name }")
    try:
        out = subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True,
                             text=True, timeout=60).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    return [line.strip() for line in out.splitlines() if line.strip()]


def speak(voice: str, text: str, path: str, pitch: str = "+0st", rate: str = "+0%") -> None:
    ssml = (f"<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='en-US'>"
            f"<prosody pitch='{pitch}' rate='{rate}'>{text}</prosody></speak>")
    script = ("Add-Type -AssemblyName System.Speech;"
              "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer;"
              f"$s.SelectVoice('{voice}'); $s.SetOutputToWaveFile('{path}'); $s.SpeakSsml(\"{ssml}\"); $s.Dispose()")
    subprocess.run(["powershell", "-NoProfile", "-Command", script], check=True, timeout=120)


@unittest.skipUnless(engine.model_dir().joinpath("embedding_model.ckpt").exists(), "model not available")
class IntegrationTests(unittest.TestCase):
    """Real model on synthesised speech (one Windows voice, with and without a pitch shift)."""

    @classmethod
    def setUpClass(cls):
        voices = sapi_voices()
        if not voices:
            raise unittest.SkipTest("no Windows speech voice installed")
        cls.folder = tempfile.TemporaryDirectory()
        text_a = "The quick brown fox jumps over the lazy dog while the sun is shining brightly today."
        text_b = "A good morning to you, please remember to bring your documents to the meeting tomorrow."
        join = lambda name: os.path.join(cls.folder.name, name)
        cls.a1, cls.a2, cls.shifted = join("a1.wav"), join("a2.wav"), join("shifted.wav")
        speak(voices[0], text_a, cls.a1)
        speak(voices[0], text_b, cls.a2)
        speak(voices[0], text_a, cls.shifted, pitch="-9st", rate="-15%")
        cls.verifier = engine.SpeakerVerifier()

    @classmethod
    def tearDownClass(cls):
        cls.folder.cleanup()

    def test_same_voice_different_text_matches(self):
        result = self.verifier.verify(self.a1, self.a2)
        self.assertEqual(result.verdict, "same")
        self.assertGreater(result.score, 0.6)

    def test_pitch_shift_does_not_break_the_match(self):
        """The model keys on timbre, so a pitch/rate change of the same voice is still recognised."""
        self.assertEqual(self.verifier.verify(self.a1, self.shifted).verdict, "same")

    def test_score_is_symmetric(self):
        forward = self.verifier.verify(self.a1, self.shifted).score
        backward = self.verifier.verify(self.shifted, self.a1).score
        self.assertAlmostEqual(forward, backward, places=4)

    def test_identical_files_match(self):
        self.assertGreater(self.verifier.verify(self.a1, self.a1).score, 0.99)


if __name__ == "__main__":
    unittest.main()
