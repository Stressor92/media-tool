# src/core/translation/format_registry.py
"""
Central registry of all known subtitle formats.
Maps SubtitleFormat enum values to their reader/writer functions.
Uses lazy imports: format modules are loaded on first access.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable
from pathlib import Path

from core.translation.models import SubtitleDocument, SubtitleFormat

logger = logging.getLogger(__name__)

ReaderFn = Callable[[Path], SubtitleDocument]
WriterFn = Callable[[SubtitleDocument, Path], None]


class FormatRegistry:
    _readers: dict[SubtitleFormat, ReaderFn] = {}
    _writers: dict[SubtitleFormat, WriterFn] = {}

    @classmethod
    def _ensure_loaded(cls) -> None:
        if cls._readers:
            return
        from core.translation.formats import ass, lrc, sbv, scc, srt, stl, ttml, vtt

        cls._readers = {
            SubtitleFormat.SRT: srt.read,
            SubtitleFormat.ASS: ass.read,
            SubtitleFormat.SSA: ass.read,
            SubtitleFormat.VTT: vtt.read,
            SubtitleFormat.TTML: ttml.read,
            SubtitleFormat.DFXP: ttml.read,
            SubtitleFormat.SCC: scc.read,
            SubtitleFormat.STL: stl.read,
            SubtitleFormat.LRC: lrc.read,
            SubtitleFormat.SBV: sbv.read,
        }
        cls._writers = {
            SubtitleFormat.SRT: srt.write,
            SubtitleFormat.ASS: ass.write,
            SubtitleFormat.VTT: vtt.write,
            SubtitleFormat.TTML: ttml.write,
            SubtitleFormat.SCC: scc.write,
            SubtitleFormat.STL: stl.write,
            SubtitleFormat.LRC: lrc.write,
            SubtitleFormat.SBV: sbv.write,
        }

    @classmethod
    def detect_format(cls, path: Path) -> SubtitleFormat:
        """Detect format via extension first, then magic bytes as fallback."""
        fmt = SubtitleFormat.from_path(path)
        if fmt != SubtitleFormat.UNKNOWN:
            return fmt
        return cls._detect_by_content(path)

    @classmethod
    def _detect_by_content(cls, path: Path) -> SubtitleFormat:
        try:
            head = path.read_bytes()[:512]
        except OSError:
            return SubtitleFormat.UNKNOWN

        # PGS magic bytes: 0x5047 ("PG")
        if head[:2] == b"PG":
            return SubtitleFormat.SUP

        text = head.decode("utf-8", errors="ignore")

        if "WEBVTT" in text:
            return SubtitleFormat.VTT
        if "<tt " in text or "<ttml" in text or "xmlns" in text:
            return SubtitleFormat.TTML
        if "Scenarist_SCC" in text:
            return SubtitleFormat.SCC
        if "[Script Info]" in text:
            return SubtitleFormat.ASS
        if text.startswith("Ÿþ") or text[:3] == "850":
            return SubtitleFormat.STL
        # SRT uses comma as ms separator; detect timestamp pattern before arrow
        if re.search(r"\d{2}:\d{2}:\d{2},\d{3}\s*-->", text):
            return SubtitleFormat.SRT

        return SubtitleFormat.UNKNOWN

    @classmethod
    def get_reader(cls, fmt: SubtitleFormat) -> ReaderFn:
        cls._ensure_loaded()
        if fmt not in cls._readers:
            raise ValueError(f"No reader for format: {fmt.value}")
        return cls._readers[fmt]

    @classmethod
    def get_writer(cls, fmt: SubtitleFormat) -> WriterFn:
        cls._ensure_loaded()
        if fmt not in cls._writers:
            raise ValueError(f"No writer for format: {fmt.value}. Available: {[f.value for f in cls._writers]}")
        return cls._writers[fmt]

    @classmethod
    def supported_read_formats(cls) -> list[SubtitleFormat]:
        cls._ensure_loaded()
        return list(cls._readers.keys())

    @classmethod
    def supported_write_formats(cls) -> list[SubtitleFormat]:
        cls._ensure_loaded()
        return list(cls._writers.keys())
