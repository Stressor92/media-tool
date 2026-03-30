# src/core/translation/models.py
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional


class SubtitleFormat(str, Enum):
    SRT = "srt"
    ASS = "ass"
    SSA = "ssa"
    VTT = "vtt"
    UNKNOWN = "unknown"

    @classmethod
    def from_path(cls, path: Path) -> "SubtitleFormat":
        return {
            ".srt": cls.SRT,
            ".ass": cls.ASS,
            ".ssa": cls.SSA,
            ".vtt": cls.VTT,
        }.get(path.suffix.lower(), cls.UNKNOWN)


class TranslationStatus(str, Enum):
    SUCCESS = "success"
    FAILED  = "failed"
    SKIPPED = "skipped"   # e.g. target language already present


@dataclass(frozen=True)
class LanguagePair:
    source: str   # ISO 639-1: "de" or "en"
    target: str

    def __str__(self) -> str:
        return f"{self.source}→{self.target}"

    @classmethod
    def de_to_en(cls) -> "LanguagePair":
        return cls(source="de", target="en")

    @classmethod
    def en_to_de(cls) -> "LanguagePair":
        return cls(source="en", target="de")


@dataclass
class SubtitleSegment:
    """A single subtitle block (index, timecodes, text)."""
    index: int
    start: str          # "00:01:23,456"  (SRT format internally)
    end: str
    text: str           # May contain line breaks (\n)
    raw_tags: str = ""  # ASS-specific tags preserved during roundtrip


@dataclass
class SubtitleDocument:
    """Parsed subtitle file — format-independent intermediate representation."""
    segments: list[SubtitleSegment]
    source_format: SubtitleFormat
    source_path: Optional[Path] = None
    language: str = "unknown"
    metadata: dict[str, str] = field(default_factory=dict)  # ASS [Script Info] etc.


@dataclass
class TranslationRequest:
    document: SubtitleDocument
    language_pair: LanguagePair
    backend: str = "opus-mt"              # "opus-mt" | "argos"
    model_size: str = "big"               # "standard" | "big"
    batch_size: int = 32                  # Segments per inference batch
    preserve_formatting: bool = True      # Keep HTML tags (<i>, <b>)
    dry_run: bool = False


@dataclass
class TranslationResult:
    status: TranslationStatus
    request: TranslationRequest
    translated_document: Optional[SubtitleDocument] = None
    output_path: Optional[Path] = None
    segments_translated: int = 0
    duration_seconds: float = 0.0
    error_message: Optional[str] = None
