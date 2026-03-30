# src/core/translation/subtitle_parser.py
"""
Parses SRT, ASS/SSA and WebVTT into SubtitleDocument.
"""
from __future__ import annotations

import re
from pathlib import Path

from core.translation.models import SubtitleDocument, SubtitleFormat, SubtitleSegment

# ── SRT ────────────────────────────────────────────────────────────────────

_SRT_BLOCK = re.compile(
    r"(\d+)\r?\n"
    r"(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})\r?\n"
    r"([\s\S]*?)(?=\n\n|\Z)",
    re.MULTILINE,
)


def parse_srt(text: str) -> list[SubtitleSegment]:
    segments: list[SubtitleSegment] = []
    for m in _SRT_BLOCK.finditer(text.strip() + "\n\n"):
        segments.append(SubtitleSegment(
            index=int(m.group(1)),
            start=m.group(2),
            end=m.group(3),
            text=m.group(4).strip(),
        ))
    return segments


# ── WebVTT ─────────────────────────────────────────────────────────────────

_VTT_BLOCK = re.compile(
    r"(\d{2}:\d{2}:\d{2}\.\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}\.\d{3})[^\n]*\n"
    r"([\s\S]*?)(?=\n\n|\Z)",
    re.MULTILINE,
)


def _vtt_to_srt_time(t: str) -> str:
    return t.replace(".", ",")


def parse_vtt(text: str) -> list[SubtitleSegment]:
    body = re.sub(r"^WEBVTT.*?\n\n", "", text, flags=re.DOTALL)
    segments: list[SubtitleSegment] = []
    for i, m in enumerate(_VTT_BLOCK.finditer(body.strip() + "\n\n"), start=1):
        segments.append(SubtitleSegment(
            index=i,
            start=_vtt_to_srt_time(m.group(1)),
            end=_vtt_to_srt_time(m.group(2)),
            text=m.group(3).strip(),
        ))
    return segments


# ── ASS / SSA ──────────────────────────────────────────────────────────────

_ASS_DIALOGUE = re.compile(
    r"^Dialogue:\s*\d+,"          # Layer
    r"(\d:\d{2}:\d{2}\.\d{2}),"  # Start
    r"(\d:\d{2}:\d{2}\.\d{2}),"  # End
    r"[^,]*,[^,]*,[^,]*,[^,]*,[^,]*,[^,]*,"  # Style, Actor, margins, effect
    r"(.*)",
    re.MULTILINE,
)
_ASS_TAG = re.compile(r"\{[^}]*\}")


def _ass_to_srt_time(t: str) -> str:
    # "0:01:23.45" → "00:01:23,450"
    h, m, rest = t.split(":")
    s, cs = rest.split(".")
    return f"{int(h):02d}:{int(m):02d}:{int(s):02d},{int(cs) * 10:03d}"


def parse_ass(text: str) -> tuple[list[SubtitleSegment], dict[str, str]]:
    metadata: dict[str, str] = {}
    for line in text.splitlines():
        if line.startswith("Title:"):
            metadata["title"] = line.split(":", 1)[1].strip()

    segments: list[SubtitleSegment] = []
    for i, m in enumerate(_ASS_DIALOGUE.finditer(text), start=1):
        raw_text = m.group(3)
        clean    = _ASS_TAG.sub("", raw_text).replace(r"\N", "\n").replace(r"\n", "\n")
        segments.append(SubtitleSegment(
            index=i,
            start=_ass_to_srt_time(m.group(1)),
            end=_ass_to_srt_time(m.group(2)),
            text=clean.strip(),
            raw_tags=raw_text,
        ))
    return segments, metadata


# ── Dispatcher ─────────────────────────────────────────────────────────────

def parse_subtitle_file(path: Path) -> SubtitleDocument:
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    fmt  = SubtitleFormat.from_path(path)

    match fmt:
        case SubtitleFormat.SRT:
            segments = parse_srt(text)
            metadata: dict[str, str] = {}
        case SubtitleFormat.VTT:
            segments = parse_vtt(text)
            metadata = {}
        case SubtitleFormat.ASS | SubtitleFormat.SSA:
            segments, metadata = parse_ass(text)
        case _:
            raise ValueError(f"Unsupported format: {path.suffix}")

    return SubtitleDocument(
        segments=segments,
        source_format=fmt,
        source_path=path,
        metadata=metadata,
    )
