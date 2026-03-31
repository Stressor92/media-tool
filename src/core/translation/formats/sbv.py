# src/core/translation/formats/sbv.py
"""
SBV (SubViewer / YouTube) format reader and writer.

Similar to SRT, but timestamp format: 0:00:01.000,0:00:03.000
"""
from __future__ import annotations

import re
from pathlib import Path

from core.translation.models import SubtitleDocument, SubtitleFormat, SubtitleSegment

_SBV_BLOCK = re.compile(
    r"(\d+:\d{2}:\d{2}\.\d{3}),(\d+:\d{2}:\d{2}\.\d{3})\r?\n([\s\S]*?)(?=\n\n|\Z)",
    re.MULTILINE,
)


def _sbv_to_srt(t: str) -> str:
    """0:01:23.456 → 00:01:23,456"""
    parts = t.split(":")
    h = parts[0].zfill(2)
    rest = ":".join(parts[1:]).replace(".", ",")
    return f"{h}:{rest}"


def _srt_to_sbv(t: str) -> str:
    """00:01:23,456 → 0:01:23.456"""
    result = t.replace(",", ".")
    # Strip leading zero from hours if present: "00:" → "0:"
    if result.startswith("0"):
        result = result.lstrip("0") or "0"
        if result.startswith(":"):
            result = "0" + result
    return result


def read(path: Path) -> SubtitleDocument:
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    segments: list[SubtitleSegment] = []
    for i, m in enumerate(_SBV_BLOCK.finditer(text.strip() + "\n\n"), start=1):
        segments.append(SubtitleSegment(
            index=i,
            start=_sbv_to_srt(m.group(1)),
            end=_sbv_to_srt(m.group(2)),
            text=m.group(3).strip(),
        ))
    return SubtitleDocument(
        segments=segments,
        source_format=SubtitleFormat.SBV,
        source_path=path,
    )


def write(doc: SubtitleDocument, path: Path) -> None:
    lines: list[str] = []
    for seg in doc.segments:
        lines.append(f"{_srt_to_sbv(seg.start)},{_srt_to_sbv(seg.end)}")
        lines.append(seg.text)
        lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
