# src/core/translation/formats/lrc.py
"""
LRC (Lyric) format reader and writer.

Format: [mm:ss.xx]Lyric text
"""

from __future__ import annotations

import re
from pathlib import Path

from core.translation.models import SubtitleDocument, SubtitleFormat, SubtitleSegment

_LRC_LINE = re.compile(r"\[(\d{2}):(\d{2})\.(\d{2,3})\](.*)")
_LRC_META = re.compile(r"\[(\w+):(.*?)\]")


def _lrc_time_to_srt(m: int, s: int, cs: int) -> str:
    ms = cs * 10 if cs < 100 else cs
    return f"00:{m:02d}:{s:02d},{ms:03d}"


def _srt_time_to_lrc(t: str) -> str:
    _, m, rest = t.split(":")
    s, ms = rest.split(",")
    cs = int(ms) // 10
    return f"{int(m):02d}:{int(s):02d}.{cs:02d}"


def _add_ms(srt_time: str, ms_add: int) -> str:
    h, m, rest = srt_time.split(":")
    s, ms = rest.split(",")
    total = int(h) * 3_600_000 + int(m) * 60_000 + int(s) * 1_000 + int(ms) + ms_add
    h2, rem = divmod(total, 3_600_000)
    m2, rem = divmod(rem, 60_000)
    s2, ms2 = divmod(rem, 1_000)
    return f"{h2:02d}:{m2:02d}:{s2:02d},{ms2:03d}"


def read(path: Path) -> SubtitleDocument:
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    metadata: dict[str, str] = {}
    lines_with_time: list[tuple[str, str]] = []

    for line in text.splitlines():
        meta = _LRC_META.match(line)
        if meta and not _LRC_LINE.match(line):
            metadata[meta.group(1)] = meta.group(2).strip()
            continue

        m = _LRC_LINE.match(line)
        if m:
            lines_with_time.append(
                (
                    _lrc_time_to_srt(int(m.group(1)), int(m.group(2)), int(m.group(3))),
                    m.group(4).strip(),
                )
            )

    segments: list[SubtitleSegment] = []
    for i, (start, content) in enumerate(lines_with_time):
        end = lines_with_time[i + 1][0] if i + 1 < len(lines_with_time) else _add_ms(start, 3000)
        if content:
            segments.append(
                SubtitleSegment(
                    index=i + 1,
                    start=start,
                    end=end,
                    text=content,
                )
            )

    return SubtitleDocument(
        segments=segments,
        source_format=SubtitleFormat.LRC,
        source_path=path,
        metadata=metadata,
    )


def write(doc: SubtitleDocument, path: Path) -> None:
    lines: list[str] = []
    for key, value in (doc.metadata or {}).items():
        lines.append(f"[{key}:{value}]")
    if lines:
        lines.append("")
    for seg in doc.segments:
        lines.append(f"[{_srt_time_to_lrc(seg.start)}]{seg.text}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
