"""Speaker verification with SpeechBrain ECAPA-TDNN: embeddings per speech window, averaged per file."""
from __future__ import annotations

import math
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

import numpy as np

from . import audio

MODEL_SOURCE = "speechbrain/spkrec-ecapa-voxceleb"
MODEL_FILES = ("hyperparams.yaml", "embedding_model.ckpt", "mean_var_norm_emb.ckpt",
               "classifier.ckpt", "label_encoder.ckpt")

THRESHOLD = 0.25            # cosine similarity decision threshold (EER point of this model)
UNCERTAIN_RANGE = 0.05      # +/- band around the threshold reported as "uncertain"
SIGMOID_STEEPNESS = 10.0    # maps the score distance from the threshold to a 0-100 confidence
MIN_SPEECH_WARNING = 3.0    # seconds of net speech below which the result is flagged
LOW_CONSISTENCY = 0.45      # per-file window similarity below which several speakers are suspected


def model_dir() -> Path:
    """Bundled model next to the exe, or the project's pretrained_models folder."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return base / "pretrained_models" / "spkrec-ecapa-voxceleb"


def confidence(score: float) -> float:
    """Score -> 0..100. 50 means exactly on the threshold, not a calibrated probability."""
    return 100.0 / (1.0 + math.exp(-SIGMOID_STEEPNESS * (score - THRESHOLD)))


def verdict_for(score: float) -> str:
    if score > THRESHOLD + UNCERTAIN_RANGE:
        return "same"
    if score < THRESHOLD - UNCERTAIN_RANGE:
        return "different"
    return "uncertain"


@dataclass
class FileInfo:
    path: str
    duration: Optional[float] = None
    speech_seconds: float = 0.0
    windows: int = 0
    consistency: Optional[float] = None   # mean similarity of the windows to the file's voice print


@dataclass
class Result:
    score: float
    prediction: bool            # the model's own same/different decision
    confidence: float
    verdict: str                # 'same' | 'different' | 'uncertain'
    files: tuple
    device: str
    seconds: float
    warnings: list = field(default_factory=list)   # [(message key, argument)]


class SpeakerVerifier:
    def __init__(self):
        import torch
        self.cuda = torch.cuda.is_available()
        self.device = "cuda" if self.cuda else "cpu"
        self.device_name = torch.cuda.get_device_name(0) if self.cuda else "CPU"
        self._model = None

    # ------------------------------------------------------------ model
    def load(self):
        if self._model is not None:
            return self._model
        try:
            from speechbrain.inference.speaker import SpeakerRecognition
        except ImportError:
            from speechbrain.pretrained.interfaces import SpeakerRecognition
        folder = model_dir()
        source = str(folder) if all((folder / name).exists() for name in MODEL_FILES) else MODEL_SOURCE
        options = {}
        try:  # copy instead of symlinking: symlinks need elevated rights on Windows
            from speechbrain.utils.fetching import LocalStrategy
            options["local_strategy"] = LocalStrategy.COPY
        except ImportError:
            pass
        self._model = SpeakerRecognition.from_hparams(
            source=source, savedir=str(folder), run_opts={"device": self.device}, **options)
        return self._model

    # ------------------------------------------------------------ embeddings
    def _embed(self, windows: list):
        """L2-normalised embedding for every window: tensor [n, dim]."""
        import torch
        model = self.load()
        longest = max(len(w) for w in windows)
        batch = torch.zeros(len(windows), longest)
        for row, window in enumerate(windows):
            batch[row, : len(window)] = torch.from_numpy(window)
        lengths = torch.tensor([len(w) / longest for w in windows])
        with torch.no_grad():
            embeddings = model.encode_batch(batch.to(self.device), lengths.to(self.device), normalize=False)
        return torch.nn.functional.normalize(embeddings.squeeze(1), dim=-1)

    def voice_print(self, path: str):
        """(voice print tensor [dim], FileInfo) for one recording."""
        import torch
        samples = audio.load_audio(path)
        speech = audio.trim_silence(samples)
        windows = audio.segments(speech)
        embeddings = self._embed(windows)
        voice_print = torch.nn.functional.normalize(embeddings.mean(dim=0), dim=-1)
        info = FileInfo(path, len(samples) / audio.SAMPLE_RATE, len(speech) / audio.SAMPLE_RATE, len(windows))
        if len(windows) > 1:
            info.consistency = float((embeddings @ voice_print).mean())
        return voice_print, info

    # ------------------------------------------------------------ verification
    def verify(self, path1: str, path2: str, progress: Optional[Callable[[str], None]] = None) -> Result:
        import torch
        started = time.time()
        say = progress or (lambda key: None)
        say("loading_model")
        self.load()
        say("analysing_1")
        first, info1 = self.voice_print(path1)
        say("analysing_2")
        second, info2 = self.voice_print(path2)
        score = float(torch.dot(first, second))
        result = Result(score=score, prediction=score > THRESHOLD, confidence=confidence(score),
                        verdict=verdict_for(score), files=(info1, info2), device=self.device_name,
                        seconds=time.time() - started)
        for number, info in enumerate((info1, info2), start=1):
            if info.speech_seconds < MIN_SPEECH_WARNING:
                result.warnings.append(("w_short", f"{number}|{info.speech_seconds:.1f}"))
            if info.consistency is not None and info.consistency < LOW_CONSISTENCY:
                result.warnings.append(("w_multi", str(number)))
        return result


def main_compare(argv: list) -> int:
    """Headless check: `--compare FILE1 FILE2 [--out REPORT.txt]` (the windowed exe has no console)."""
    out = None
    if "--out" in argv:
        position = argv.index("--out")
        out = argv[position + 1] if position + 1 < len(argv) else None
        argv = argv[:position] + argv[position + 2:]
    lines = []
    if len(argv) != 2:
        lines.append("usage: --compare FILE1 FILE2 [--out REPORT.txt]")
        code = 2
    else:
        code = 0
        try:
            result = SpeakerVerifier().verify(argv[0], argv[1])
            lines.append(f"score={result.score:.4f} confidence={result.confidence:.1f}% "
                         f"verdict={result.verdict} device={result.device} seconds={result.seconds:.1f}")
            for info in result.files:
                lines.append(f"  {os.path.basename(info.path)}: {info.duration:.1f}s, speech "
                             f"{info.speech_seconds:.1f}s, windows={info.windows}, consistency={info.consistency}")
            lines += [f"  warning: {w}" for w in result.warnings]
        except Exception as e:
            lines.append(f"error: {type(e).__name__}: {e}")
            code = 1
    text = "\n".join(lines)
    if out:
        Path(out).write_text(text, encoding="utf-8")
    elif sys.stdout is not None:
        print(text)
    return code
