"""Hungarian / English strings and the persisted language choice."""
from __future__ import annotations

import ctypes
import json
import os
from pathlib import Path

from . import APP_NAME, AUTHOR, YEAR, __version__

LANGS = {"hu": "Magyar", "en": "English"}

STRINGS = {
    "hu": {
        "title": "Hangazonosító",
        "subtitle": "Két hangfelvétel összehasonlítása: ugyanaz a személy beszél?",
        "credit": "Készítette: {a} - {y}",
        "disclaimer": "Nem hivatalos program. Az eredmény tájékoztató jellegű becslés, nem igazságügyi szakértői vélemény, és jogi eljárásban nem használható bizonyítékként.",
        "language": "Nyelv",
        "files": "Hangfájlok",
        "file1": "1. hangfájl",
        "file2": "2. hangfájl",
        "browse": "Tallózás...",
        "browse_title": "Hangfájl kiválasztása",
        "filter_audio": "Hangfájlok",
        "filter_all": "Minden fájl",
        "identify": "Azonosítás",
        "clear": "Törlés",
        "copy": "Eredmény másolása",
        "copied": "Az eredmény a vágólapra került.",
        "result": "Eredmény",
        "confidence_hint": "50% = határeset · 100% = egyértelmű egyezés",
        "gauge_different": "más személy",
        "gauge_same": "ugyanaz",
        "verdict_same": "Ugyanaz a személy beszél",
        "verdict_different": "Más személy beszél",
        "verdict_uncertain": "Bizonytalan, a határérték közelében",
        "m_score": "Hasonlóság (cosine)",
        "m_threshold": "Küszöbérték",
        "m_model": "Modell döntése",
        "m_model_same": "ugyanaz",
        "m_model_different": "különböző",
        "m_speech": "Tiszta beszéd",
        "m_consistency": "Hang egyöntetűsége",
        "m_device": "Számítás",
        "m_time": "Futási idő",
        "file_info": "{d} · tiszta beszéd: {s}",
        "reading": "Fájl olvasása...",
        "ready": "Készen áll az azonosításra",
        "loading_model": "A modell betöltése...",
        "analysing_1": "Az 1. felvétel elemzése...",
        "analysing_2": "A 2. felvétel elemzése...",
        "done": "Azonosítás befejezve",
        "failed": "Az azonosítás nem sikerült",
        "device_gpu": "{n} (CUDA)",
        "device_cpu": "Processzor (CPU)",
        "need_files": "Válassz ki mindkét hangfájlt.",
        "w_short": "A(z) {n}. felvételen csak {s} s tiszta beszéd van, az eredmény kevésbé megbízható. Ajánlott: legalább 3–5 s.",
        "w_multi": "A(z) {n}. felvételen nem egyöntetű a hang, lehet, hogy több személy beszél.",
        "err_missing": "A fájl nem található: {a}",
        "err_empty": "A fájl üres vagy nem hallható benne hang: {a}",
        "err_need_ffmpeg": "A(z) {a} formátumhoz FFmpeg szükséges. Telepítés: winget install ffmpeg. A WAV, MP3, FLAC és OGG külső eszköz nélkül működik.",
        "err_decode": "A hangfájlt nem sikerült beolvasni: {a}",
        "err_model": "A modell betöltése nem sikerült: {a}",
        "err_generic": "Hiba: {a}",
        "days": "",
    },
    "en": {
        "title": "Hangazonosító",
        "subtitle": "Compare two recordings: is the same person speaking?",
        "credit": "Created by: {a} - {y}",
        "disclaimer": "Unofficial software. The result is an informative estimate, not a forensic expert opinion, and must not be used as evidence in legal proceedings.",
        "language": "Language",
        "files": "Audio files",
        "file1": "Audio file 1",
        "file2": "Audio file 2",
        "browse": "Browse...",
        "browse_title": "Select an audio file",
        "filter_audio": "Audio files",
        "filter_all": "All files",
        "identify": "Verify",
        "clear": "Clear",
        "copy": "Copy result",
        "copied": "The result was copied to the clipboard.",
        "result": "Result",
        "confidence_hint": "50% = borderline · 100% = clear match",
        "gauge_different": "different person",
        "gauge_same": "same person",
        "verdict_same": "The same person is speaking",
        "verdict_different": "Different people are speaking",
        "verdict_uncertain": "Uncertain, close to the threshold",
        "m_score": "Similarity (cosine)",
        "m_threshold": "Threshold",
        "m_model": "Model decision",
        "m_model_same": "same",
        "m_model_different": "different",
        "m_speech": "Net speech",
        "m_consistency": "Voice consistency",
        "m_device": "Compute",
        "m_time": "Run time",
        "file_info": "{d} · net speech: {s}",
        "reading": "Reading file...",
        "ready": "Ready to verify",
        "loading_model": "Loading the model...",
        "analysing_1": "Analysing recording 1...",
        "analysing_2": "Analysing recording 2...",
        "done": "Verification finished",
        "failed": "Verification failed",
        "device_gpu": "{n} (CUDA)",
        "device_cpu": "Processor (CPU)",
        "need_files": "Select both audio files.",
        "w_short": "Recording {n} has only {s} s of net speech, so the result is less reliable. Recommended: at least 3-5 s.",
        "w_multi": "The voice in recording {n} is not consistent; more than one person may be speaking.",
        "err_missing": "File not found: {a}",
        "err_empty": "The file is empty or contains no audible sound: {a}",
        "err_need_ffmpeg": "The {a} format needs FFmpeg. Install it with: winget install ffmpeg. WAV, MP3, FLAC and OGG work without any external tool.",
        "err_decode": "Could not read the audio file: {a}",
        "err_model": "Could not load the model: {a}",
        "err_generic": "Error: {a}",
        "days": "",
    },
}


def tr(lang: str, key: str, **kwargs) -> str:
    table = STRINGS.get(lang) or STRINGS["en"]
    return table.get(key, STRINGS["en"].get(key, key)).format(**kwargs)


def credit_text(lang: str) -> str:
    return f"v{__version__}  ·  " + tr(lang, "credit", a=AUTHOR, y=YEAR)


def detect_system_language() -> str:
    try:
        return "hu" if (ctypes.windll.kernel32.GetUserDefaultUILanguage() & 0x3FF) == 0x0E else "en"
    except (OSError, AttributeError):
        return "en"


def settings_path() -> Path:
    base = Path(os.environ.get("APPDATA", Path.home())) / APP_NAME
    base.mkdir(parents=True, exist_ok=True)
    return base / "settings.json"


def load_language() -> str:
    try:
        saved = json.loads(settings_path().read_text(encoding="utf-8")).get("language")
        if saved in LANGS:
            return saved
    except (OSError, ValueError):
        pass
    return detect_system_language()


def save_language(lang: str) -> None:
    try:
        settings_path().write_text(json.dumps({"language": lang}), encoding="utf-8")
    except OSError:
        pass
