"""Audio loading and preprocessing: mono 16 kHz, silence removal, fixed-length segments."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Optional

import numpy as np

SAMPLE_RATE = 16_000
FRAME = SAMPLE_RATE * 30 // 1000          # 30 ms analysis frames
SILENCE_DB = 30.0                         # frames this far below the loud level count as silence
MIN_SPEECH_SECONDS = 1.0                  # below this the trimming is skipped (nothing reliable to keep)
SEGMENT_SECONDS = 6.0
SEGMENT_HOP_SECONDS = 3.0
MIN_SEGMENT_SECONDS = 2.0

NEEDS_FFMPEG = {".m4a", ".aac", ".wma", ".opus", ".mp4", ".webm"}


class AudioError(Exception):
    """A loading failure; `key` selects the translated message."""

    def __init__(self, key: str, arg: str = ""):
        super().__init__(key)
        self.key = key
        self.arg = arg


def _decode_with_ffmpeg(path: str) -> np.ndarray:
    """Decodes any format to mono 16 kHz float32 using FFmpeg, if it is installed."""
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise AudioError("err_need_ffmpeg", Path(path).suffix.lower())
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    process = subprocess.run(
        [ffmpeg, "-v", "error", "-i", path, "-f", "f32le", "-ac", "1", "-ar", str(SAMPLE_RATE), "-"],
        capture_output=True, creationflags=flags)
    if process.returncode != 0 or not process.stdout:
        raise AudioError("err_decode", process.stderr.decode(errors="ignore")[:120])
    return np.frombuffer(process.stdout, dtype=np.float32).copy()


def _resample(samples: np.ndarray, rate: int) -> np.ndarray:
    if rate == SAMPLE_RATE:
        return samples
    import torch
    import torchaudio.functional as F
    resampled = F.resample(torch.from_numpy(samples), rate, SAMPLE_RATE)
    return resampled.numpy()


def duration_seconds(path: str) -> Optional[float]:
    try:
        import soundfile
        return float(soundfile.info(path).duration)
    except Exception:
        return None


def load_audio(path: str) -> np.ndarray:
    """Mono float32 samples at 16 kHz. WAV/FLAC/OGG/MP3 need no external tool; others use FFmpeg."""
    if not Path(path).is_file():
        raise AudioError("err_missing", path)
    try:
        import soundfile
        data, rate = soundfile.read(path, dtype="float32", always_2d=True)
        samples = _resample(data.mean(axis=1), rate)
    except AudioError:
        raise
    except Exception:
        samples = _decode_with_ffmpeg(path)
    if samples.size == 0:
        raise AudioError("err_empty", Path(path).name)
    return samples - float(np.mean(samples))  # remove DC offset


def trim_silence(samples: np.ndarray) -> np.ndarray:
    """Keeps only the speech: frames within SILENCE_DB of the loud level, padded by two frames."""
    count = len(samples) // FRAME
    if count < 4:
        return samples
    frames = samples[: count * FRAME].reshape(count, FRAME)
    level = 20 * np.log10(np.sqrt(np.mean(frames ** 2, axis=1)) + 1e-9)
    keep = level >= max(np.percentile(level, 95) - SILENCE_DB, -75.0)
    keep = np.convolve(keep.astype(float), np.ones(5), mode="same") > 0   # dilate by two frames
    speech = frames[keep].reshape(-1)
    return speech if len(speech) >= SAMPLE_RATE * MIN_SPEECH_SECONDS else samples


def segments(samples: np.ndarray) -> list:
    """Overlapping windows (6 s, hop 3 s). Short audio stays a single segment; a tiny tail is merged."""
    size, hop = int(SEGMENT_SECONDS * SAMPLE_RATE), int(SEGMENT_HOP_SECONDS * SAMPLE_RATE)
    if len(samples) <= size:
        return [samples]
    starts = list(range(0, len(samples) - size + 1, hop))
    if starts[-1] + size < len(samples):
        starts.append(len(samples) - size)       # last window ends exactly at the end of the audio
    return [samples[s:s + size] for s in starts]
