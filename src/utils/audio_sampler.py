# src/utils/audio_sampler.py
"""
Extrahiert ein kurzes Audio-Sample aus einer Videodatei.
Ausgabe: temporäre WAV-Datei (16kHz, Mono) — Whisper-optimiert.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from utils.ffmpeg_runner import run_ffmpeg


def extract_audio_sample(
    video_path: Path,
    duration: int = 30,
    offset: int = 120,
    stream_index: int = 0,
) -> Path:
    """
    Extrahiert `duration` Sekunden Audio ab `offset` Sekunden.
    Gibt einen temporären WAV-Pfad zurück.

    Args:
        video_path:    Eingabe-Videodatei
        duration:      Sample-Länge in Sekunden (Standard: 30)
        offset:        Start-Offset in Sekunden (Standard: 120 — Intro überspringen)
        stream_index:  Index der Audiospur (0-basiert)

    Returns:
        Pfad zur temporären WAV-Datei (muss vom Aufrufer gelöscht werden)
    """
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp.close()
    out_path = Path(tmp.name)

    # 16kHz Mono WAV — optimales Format für Whisper und AcoustID
    args = [
        "-y",
        "-ss",
        str(offset),
        "-i",
        str(video_path),
        "-t",
        str(duration),
        "-map",
        f"0:a:{stream_index}",
        "-ar",
        "16000",  # 16kHz Sample-Rate
        "-ac",
        "1",  # Mono
        "-acodec",
        "pcm_s16le",  # Unkomprimiertes PCM
        "-vn",  # Kein Video
        str(out_path),
    ]
    result = run_ffmpeg(args)
    if not result.success or not out_path.exists():
        out_path.unlink(missing_ok=True)
        raise RuntimeError(f"Audio-Extraktion fehlgeschlagen für {video_path.name}: {result.stderr[:200]}")
    return out_path
