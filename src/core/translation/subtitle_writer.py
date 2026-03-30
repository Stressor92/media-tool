# src/core/translation/subtitle_writer.py
from __future__ import annotations

import logging
from pathlib import Path

from core.translation.models import SubtitleDocument, SubtitleFormat

logger = logging.getLogger(__name__)


def _segments_to_srt(doc: SubtitleDocument) -> str:
    lines: list[str] = []
    for seg in doc.segments:
        lines.append(str(seg.index))
        lines.append(f"{seg.start} --> {seg.end}")
        lines.append(seg.text)
        lines.append("")
    return "\n".join(lines)


def _srt_time_to_vtt(t: str) -> str:
    return t.replace(",", ".")


def _segments_to_vtt(doc: SubtitleDocument) -> str:
    lines = ["WEBVTT", ""]
    for seg in doc.segments:
        lines.append(f"{_srt_time_to_vtt(seg.start)} --> {_srt_time_to_vtt(seg.end)}")
        lines.append(seg.text)
        lines.append("")
    return "\n".join(lines)


def write_subtitle_file(
    doc: SubtitleDocument,
    output_path: Path,
    output_format: SubtitleFormat | None = None,
) -> None:
    """
    Writes a SubtitleDocument to the desired file.
    If no format is specified, the source format is preserved.
    ASS→SRT downgrade is explicitly allowed (tags are lost, warning is logged).
    """
    fmt = output_format or doc.source_format
    if fmt == SubtitleFormat.UNKNOWN:
        fmt = SubtitleFormat.SRT

    if fmt == SubtitleFormat.SRT:
        content = _segments_to_srt(doc)
    elif fmt == SubtitleFormat.VTT:
        content = _segments_to_vtt(doc)
    elif fmt in (SubtitleFormat.ASS, SubtitleFormat.SSA):
        # Full ASS roundtrip is out-of-scope for v1 — write as SRT
        logger.warning(
            "ASS/SSA roundtrip not fully supported — writing as SRT: %s",
            output_path.name,
        )
        content = _segments_to_srt(doc)
    else:
        content = _segments_to_srt(doc)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")
