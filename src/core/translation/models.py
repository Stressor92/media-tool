# src/core/translation/models.py
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class SubtitleFormat(str, Enum):
    SRT = "srt"
    ASS = "ass"
    SSA = "ssa"
    VTT = "vtt"
    TTML = "ttml"
    DFXP = "dfxp"  # Alias for TTML
    SCC = "scc"
    STL = "stl"
    LRC = "lrc"
    SBV = "sbv"
    SUB = "sub"  # VobSub (Bitmap)
    SUP = "sup"  # PGS   (Bitmap)
    UNKNOWN = "unknown"

    @classmethod
    def from_path(cls, path: Path) -> SubtitleFormat:
        return {
            ".srt": cls.SRT,
            ".ass": cls.ASS,
            ".ssa": cls.SSA,
            ".vtt": cls.VTT,
            ".ttml": cls.TTML,
            ".dfxp": cls.DFXP,
            ".xml": cls.TTML,
            ".scc": cls.SCC,
            ".stl": cls.STL,
            ".lrc": cls.LRC,
            ".sbv": cls.SBV,
            ".sub": cls.SUB,
            ".sup": cls.SUP,
            ".idx": cls.SUB,  # VobSub index
        }.get(path.suffix.lower(), cls.UNKNOWN)

    @property
    def is_bitmap(self) -> bool:
        return self in (SubtitleFormat.SUB, SubtitleFormat.SUP)

    @property
    def is_text_based(self) -> bool:
        return not self.is_bitmap and self != SubtitleFormat.UNKNOWN


class TranslationStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"  # e.g. target language already present


@dataclass(frozen=True)
class LanguagePair:
    source: str  # ISO 639-1: "de" or "en"
    target: str

    def __str__(self) -> str:
        return f"{self.source}→{self.target}"

    @classmethod
    def de_to_en(cls) -> LanguagePair:
        return cls(source="de", target="en")

    @classmethod
    def en_to_de(cls) -> LanguagePair:
        return cls(source="en", target="de")


@dataclass
class StyleInfo:
    """Format-independent style description, preserved as far as possible during roundtrip."""

    name: str = "Default"
    font_name: str = "Arial"
    font_size: int = 20
    bold: bool = False
    italic: bool = False
    underline: bool = False
    primary_color: str = "#FFFFFF"
    outline_color: str = "#000000"
    background_color: str = "#000000"
    margin_left: int = 10
    margin_right: int = 10
    margin_vertical: int = 10
    alignment: int = 2  # SSA/ASS numpad notation: 2 = bottom-center


@dataclass
class PositionInfo:
    """Optional positioning for a segment (TTML regions, ASS \\pos)."""

    x: float | None = None  # 0.0–1.0 relative to width
    y: float | None = None  # 0.0–1.0 relative to height
    region: str | None = None  # TTML region ID


@dataclass
class SubtitleSegment:
    """A single subtitle block (index, timecodes, text)."""

    index: int
    start: str  # "00:01:23,456"  (SRT format internally)
    end: str
    text: str  # May contain line breaks (\n)
    raw_tags: str = ""  # ASS-specific tags preserved during roundtrip
    style_name: str = "Default"
    position: PositionInfo | None = None
    actor: str = ""  # ASS Actor / speaker label


@dataclass
class SubtitleDocument:
    """Parsed subtitle file — format-independent intermediate representation."""

    segments: list[SubtitleSegment]
    source_format: SubtitleFormat
    source_path: Path | None = None
    language: str = "unknown"
    metadata: dict[str, str] = field(default_factory=dict)  # ASS [Script Info] etc.
    styles: list[StyleInfo] = field(default_factory=list)
    frame_rate: float = 25.0  # For SCC / frame-based formats
    video_width: int = 1920  # For relative positioning
    video_height: int = 1080


@dataclass
class TranslationRequest:
    document: SubtitleDocument
    language_pair: LanguagePair
    backend: str = "opus-mt"  # "opus-mt" | "argos"
    model_size: str = "big"  # "standard" | "big"
    batch_size: int = 32  # Segments per inference batch
    preserve_formatting: bool = True  # Keep HTML tags (<i>, <b>)
    dry_run: bool = False


@dataclass
class TranslationResult:
    status: TranslationStatus
    request: TranslationRequest
    translated_document: SubtitleDocument | None = None
    output_path: Path | None = None
    segments_translated: int = 0
    duration_seconds: float = 0.0
    error_message: str | None = None
