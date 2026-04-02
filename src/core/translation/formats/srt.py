# src/core/translation/formats/srt.py
"""SRT (SubRip) format reader and writer."""

from __future__ import annotations

import re
from pathlib import Path

from core.translation.models import SubtitleDocument, SubtitleFormat, SubtitleSegment

_SRT_BLOCK = re.compile(
    r"(\d+)\r?\n" r"(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})\r?\n" r"([\s\S]*?)(?=\n\n|\Z)",
    re.MULTILINE,
)


def read(path: Path) -> SubtitleDocument:
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    segments: list[SubtitleSegment] = []
    for m in _SRT_BLOCK.finditer(text.strip() + "\n\n"):
        segments.append(
            SubtitleSegment(
                index=int(m.group(1)),
                start=m.group(2),
                end=m.group(3),
                text=m.group(4).strip(),
            )
        )
    return SubtitleDocument(
        segments=segments,
        source_format=SubtitleFormat.SRT,
        source_path=path,
    )


def write(doc: SubtitleDocument, path: Path) -> None:
    lines: list[str] = []
    for seg in doc.segments:
        lines.append(str(seg.index))
        lines.append(f"{seg.start} --> {seg.end}")
        lines.append(seg.text)
        lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
