# src/core/translation/formats/scc.py
"""
SCC (Scenarist Closed Captions) – CEA-608 decoder/encoder.

SCC encodes subtitles as 2-byte hex pairs per frame.
This implementation decodes the basic character set (Channel 1, Pop-On mode).
"""
from __future__ import annotations

import re
from pathlib import Path

from core.translation.models import SubtitleDocument, SubtitleFormat, SubtitleSegment

_TIMESTAMP_RE = re.compile(r"(\d{2}):(\d{2}):(\d{2});(\d{2})")

# Pop-On mode control codes (channel 1)
_CTRL_ERASE_NON_DISPLAYED    = 0x142C
_CTRL_END_OF_CAPTION         = 0x142F
_CTRL_RESUME_CAPTION_LOADING = 0x1420


def _frames_to_ms(h: int, m: int, s: int, f: int, fps: float = 29.97) -> int:
    total_frames = (h * 3600 + m * 60 + s) * fps + f
    return int(total_frames / fps * 1000)


def _ms_to_srt_time(ms: int) -> str:
    h, rem  = divmod(ms, 3_600_000)
    m, rem  = divmod(rem, 60_000)
    s, ms_r = divmod(rem, 1_000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms_r:03d}"


def _srt_time_to_ms(t: str) -> int:
    h, m, rest = t.split(":")
    s, ms = rest.split(",")
    return int(h) * 3_600_000 + int(m) * 60_000 + int(s) * 1_000 + int(ms)


def _decode_scc_pair(word: int) -> str:
    b1 = (word >> 8) & 0x7F
    b2 = word & 0x7F
    if b1 == 0x00 and b2 == 0x00:
        return ""
    chars = ""
    if 0x20 <= b1 <= 0x7E:
        chars += chr(b1)
    if 0x20 <= b2 <= 0x7E:
        chars += chr(b2)
    return chars


def read(path: Path) -> SubtitleDocument:
    text = path.read_text(encoding="utf-8", errors="replace")
    segments: list[SubtitleSegment] = []
    pending_text = ""
    pending_start_ms: int | None = None
    index = 0

    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("Scenarist"):
            continue

        ts_match = _TIMESTAMP_RE.match(line)
        if not ts_match:
            continue

        h, m, s, f = (int(x) for x in ts_match.groups())
        current_ms = _frames_to_ms(h, m, s, f)

        hex_pairs = line.split("\t", 1)[1].strip() if "\t" in line else ""

        for word_str in hex_pairs.split():
            try:
                word = int(word_str, 16)
            except ValueError:
                continue

            if word in (_CTRL_ERASE_NON_DISPLAYED, _CTRL_RESUME_CAPTION_LOADING):
                continue

            if word == _CTRL_END_OF_CAPTION:
                if pending_text.strip() and pending_start_ms is not None:
                    index += 1
                    segments.append(SubtitleSegment(
                        index=index,
                        start=_ms_to_srt_time(pending_start_ms),
                        end=_ms_to_srt_time(current_ms),
                        text=pending_text.strip(),
                    ))
                pending_text = ""
                pending_start_ms = None
                continue

            decoded = _decode_scc_pair(word)
            if decoded:
                if pending_start_ms is None:
                    pending_start_ms = current_ms
                pending_text += decoded

    return SubtitleDocument(
        segments=segments,
        source_format=SubtitleFormat.SCC,
        source_path=path,
    )


def write(doc: SubtitleDocument, path: Path) -> None:
    """Write SubtitleDocument as SCC (Pop-On mode, ASCII only)."""
    fps = doc.frame_rate or 29.97
    lines = ["Scenarist_SCC V1.0", ""]

    def ms_to_scc_ts(ms: int) -> str:
        total_s, ms_r = divmod(ms, 1000)
        h, rem = divmod(total_s, 3600)
        m, s   = divmod(rem, 60)
        f = int(ms_r / 1000 * fps)
        return f"{h:02d}:{m:02d}:{s:02d};{f:02d}"

    for seg in doc.segments:
        start_ms = _srt_time_to_ms(seg.start)
        text = seg.text[:32]

        pairs: list[str] = []
        for i in range(0, len(text), 2):
            chunk = text[i:i + 2].ljust(2)
            b1 = ord(chunk[0]) & 0x7F
            b2 = ord(chunk[1]) & 0x7F
            pairs.append(f"{b1:02x}{b2:02x}")

        payload = " ".join(["142c"] + pairs + ["142f"])
        lines.append(f"{ms_to_scc_ts(start_ms)}\t{payload}")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
