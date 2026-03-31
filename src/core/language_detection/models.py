# src/core/language_detection/models.py
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Optional


class DetectionMethod(str, Enum):
    HEURISTIC = "heuristic"    # Stufe 1: Pfad / Container-Tags
    ACOUSTID  = "acoustid"     # Stufe 2: Audio-Fingerprint
    WHISPER   = "whisper"      # Stufe 3: Speech Recognition
    MANUAL    = "manual"       # Manuell gesetzt (CLI-Override)
    UNKNOWN   = "unknown"      # Konnte nicht erkannt werden


class TaggingStatus(Enum):
    SUCCESS        = auto()
    SKIPPED        = auto()   # Sprache bereits gesetzt
    FAILED         = auto()
    LOW_CONFIDENCE = auto()   # Erkannt, aber unter Schwellwert


@dataclass(frozen=True)
class LanguageDetectionResult:
    """Ergebnis der Spracherkennung für eine Audiospur."""

    language: str              # ISO 639-2: "ger", "eng", "fra", …
    confidence: float          # 0.0 – 1.0
    method: DetectionMethod
    stream_index: int = 0      # Index der Audiospur in der Datei
    alternatives: tuple[tuple[str, float], ...] = ()  # (lang, conf) Alternativen
    raw_scores: dict[str, float] = field(default_factory=dict)


@dataclass
class DetectionRequest:
    video_path: Path
    stream_index: int = 0          # Welche Audiospur (0 = erste)
    sample_duration: int = 30      # Sekunden Audio für Whisper
    sample_offset: int = 120       # Sekunden vom Anfang überspringen (Intro)
    min_confidence: float = 0.85
    force_whisper: bool = False    # Stufe 1+2 überspringen
    dry_run: bool = False


@dataclass
class TaggingResult:
    status: TaggingStatus
    path: Path
    stream_index: int
    detected_language: Optional[str] = None
    previous_language: Optional[str] = None
    confidence: float = 0.0
    method: DetectionMethod = DetectionMethod.UNKNOWN
    error: Optional[str] = None
    output_path: Optional[Path] = None


@dataclass
class BatchTaggingResult:
    results: list[TaggingResult]

    @property
    def succeeded(self) -> list[TaggingResult]:
        return [r for r in self.results if r.status == TaggingStatus.SUCCESS]

    @property
    def failed(self) -> list[TaggingResult]:
        return [r for r in self.results if r.status == TaggingStatus.FAILED]

    @property
    def skipped(self) -> list[TaggingResult]:
        return [r for r in self.results if r.status == TaggingStatus.SKIPPED]
