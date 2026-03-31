# src/core/translation/formats/stl.py
"""
EBU STL (EBU Tech 3264) binary format reader and writer.

Structure:
  - GSI Block: 1024 bytes of metadata
  - TTI Blocks: 128 bytes per subtitle unit
"""
from __future__ import annotations

from pathlib import Path

from core.translation.models import SubtitleDocument, SubtitleFormat, SubtitleSegment

_GSI_SIZE = 1024
_TTI_SIZE = 128
_GSI_FRAMERATE_MAP: dict[bytes, int] = {b"24": 24, b"25": 25, b"30": 30}


def _stl_tc_to_srt(h: int, m: int, s: int, f: int, fps: float) -> str:
    total_ms = int((h * 3600 + m * 60 + s + f / fps) * 1000)
    h2, rem  = divmod(total_ms, 3_600_000)
    m2, rem  = divmod(rem, 60_000)
    s2, ms   = divmod(rem, 1_000)
    return f"{h2:02d}:{m2:02d}:{s2:02d},{ms:03d}"


def _decode_stl_text(raw: bytes) -> str:
    text = ""
    for b in raw:
        if b == 0x8F:
            break
        if b == 0x8A:
            text += "\n"
        elif 0x20 <= b <= 0x7E:
            text += chr(b)
    return text.strip()


def read(path: Path) -> SubtitleDocument:
    data = path.read_bytes()
    if len(data) < _GSI_SIZE:
        raise ValueError(f"File too small for STL: {len(data)} bytes")

    gsi = data[:_GSI_SIZE]

    fps_raw = gsi[256:258].rstrip(b"\x00").rstrip()
    fps = float(_GSI_FRAMERATE_MAP.get(fps_raw, 25))

    lang_raw = gsi[262:265].decode("ascii", errors="ignore").strip()

    try:
        tti_count = int(gsi[238:243].decode("ascii").strip())
    except ValueError:
        tti_count = (len(data) - _GSI_SIZE) // _TTI_SIZE

    segments: list[SubtitleSegment] = []
    metadata: dict[str, str] = {"language_code": lang_raw}

    for i in range(tti_count):
        offset = _GSI_SIZE + i * _TTI_SIZE
        if offset + _TTI_SIZE > len(data):
            break

        tti = data[offset:offset + _TTI_SIZE]
        tci = tti[5:9]
        tco = tti[9:13]
        if len(tci) < 4 or len(tco) < 4:
            continue

        start = _stl_tc_to_srt(tci[0], tci[1], tci[2], tci[3], fps)
        end   = _stl_tc_to_srt(tco[0], tco[1], tco[2], tco[3], fps)
        text  = _decode_stl_text(tti[16:128])

        if text:
            segments.append(SubtitleSegment(
                index=len(segments) + 1,
                start=start,
                end=end,
                text=text,
            ))

    return SubtitleDocument(
        segments=segments,
        source_format=SubtitleFormat.STL,
        source_path=path,
        language=lang_raw,
        frame_rate=fps,
        metadata=metadata,
    )


def write(doc: SubtitleDocument, path: Path) -> None:
    fps = int(doc.frame_rate or 25)
    fps_bytes = str(fps).encode("ascii").ljust(2)

    gsi = bytearray(1024)
    gsi[0:3]     = b"850"
    gsi[3:11]    = b"STL25.01"
    gsi[11]      = 0x01
    gsi[256:258] = fps_bytes
    lang = (doc.language or "unk").encode("ascii")[:3].ljust(3)
    gsi[262:265] = lang
    count_str = str(len(doc.segments)).encode("ascii").rjust(5)
    gsi[238:243] = count_str

    tti_blocks = bytearray()
    for seg in doc.segments:
        tti = bytearray(128)
        for tc_str, offset in [(seg.start, 5), (seg.end, 9)]:
            try:
                h, m, rest = tc_str.split(":")
                s, ms = rest.split(",")
                f = int(int(ms) / 1000 * fps)
                tti[offset:offset + 4] = bytes([int(h), int(m), int(s), f])
            except (ValueError, IndexError):
                pass

        raw_text = bytearray()
        for line in seg.text.split("\n"):
            raw_text.extend(line[:32].encode("ascii", errors="replace"))
            raw_text.append(0x8A)
        raw_text.append(0x8F)
        tti[16:16 + min(len(raw_text), 112)] = raw_text[:112]
        tti_blocks.extend(tti)

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(bytes(gsi) + bytes(tti_blocks))
