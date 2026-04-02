# src/core/translation/formats/vtt.py
"""WebVTT format reader and writer."""

from __future__ import annotations

import re
from pathlib import Path

from core.translation.models import SubtitleDocument, SubtitleFormat, SubtitleSegment

_VTT_BLOCK = re.compile(
    r"(\d{2}:\d{2}:\d{2}\.\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}\.\d{3})[^\n]*\n" r"([\s\S]*?)(?=\n\n|\Z)",
    re.MULTILINE,
)


def _vtt_to_srt(t: str) -> str:
    return t.replace(".", ",")


def _srt_to_vtt(t: str) -> str:
    return t.replace(",", ".")


def read(path: Path) -> SubtitleDocument:
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    # Strip WEBVTT header: everything up to and including the first blank line
    body = re.sub(r"^WEBVTT.*?\n\n", "", text, count=1, flags=re.DOTALL)
    segments: list[SubtitleSegment] = []
    for i, m in enumerate(_VTT_BLOCK.finditer(body.strip() + "\n\n"), start=1):
        seg_text = m.group(3).strip()
        segments.append(
            SubtitleSegment(
                index=i,
                start=_vtt_to_srt(m.group(1)),
                end=_vtt_to_srt(m.group(2)),
                text=seg_text,
            )
        )
    return SubtitleDocument(
        segments=segments,
        source_format=SubtitleFormat.VTT,
        source_path=path,
    )


def write(doc: SubtitleDocument, path: Path) -> None:
    lines = ["WEBVTT", ""]
    for seg in doc.segments:
        lines.append(f"{_srt_to_vtt(seg.start)} --> {_srt_to_vtt(seg.end)}")
        lines.append(seg.text)
        lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
