# tests/unit/test_format_registry.py
from pathlib import Path

import pytest

from core.translation.format_registry import FormatRegistry
from core.translation.models import SubtitleFormat


class TestDetectFormat:
    def test_srt_by_extension(self, tmp_path: Path) -> None:
        f = tmp_path / "sub.srt"
        f.touch()
        assert FormatRegistry.detect_format(f) == SubtitleFormat.SRT

    def test_ass_by_extension(self, tmp_path: Path) -> None:
        f = tmp_path / "sub.ass"
        f.touch()
        assert FormatRegistry.detect_format(f) == SubtitleFormat.ASS

    def test_vtt_by_extension(self, tmp_path: Path) -> None:
        f = tmp_path / "sub.vtt"
        f.touch()
        assert FormatRegistry.detect_format(f) == SubtitleFormat.VTT

    def test_ttml_by_extension(self, tmp_path: Path) -> None:
        f = tmp_path / "sub.ttml"
        f.touch()
        assert FormatRegistry.detect_format(f) == SubtitleFormat.TTML

    def test_scc_by_extension(self, tmp_path: Path) -> None:
        f = tmp_path / "sub.scc"
        f.touch()
        assert FormatRegistry.detect_format(f) == SubtitleFormat.SCC

    def test_stl_by_extension(self, tmp_path: Path) -> None:
        f = tmp_path / "sub.stl"
        f.touch()
        assert FormatRegistry.detect_format(f) == SubtitleFormat.STL

    def test_lrc_by_extension(self, tmp_path: Path) -> None:
        f = tmp_path / "sub.lrc"
        f.touch()
        assert FormatRegistry.detect_format(f) == SubtitleFormat.LRC

    def test_sbv_by_extension(self, tmp_path: Path) -> None:
        f = tmp_path / "sub.sbv"
        f.touch()
        assert FormatRegistry.detect_format(f) == SubtitleFormat.SBV

    def test_sub_by_extension(self, tmp_path: Path) -> None:
        f = tmp_path / "sub.sub"
        f.touch()
        assert FormatRegistry.detect_format(f) == SubtitleFormat.SUB

    def test_sup_by_extension(self, tmp_path: Path) -> None:
        f = tmp_path / "sub.sup"
        f.touch()
        assert FormatRegistry.detect_format(f) == SubtitleFormat.SUP

    def test_vtt_by_magic_bytes(self, tmp_path: Path) -> None:
        f = tmp_path / "sub.txt"
        f.write_text("WEBVTT\n\n00:00:01.000 --> 00:00:02.000\nHello")
        assert FormatRegistry.detect_format(f) == SubtitleFormat.VTT

    def test_pgs_by_magic_bytes(self, tmp_path: Path) -> None:
        f = tmp_path / "sub.bin"
        f.write_bytes(b"PG\x00\x00" + b"\x00" * 100)
        assert FormatRegistry.detect_format(f) == SubtitleFormat.SUP

    def test_srt_by_magic_bytes(self, tmp_path: Path) -> None:
        f = tmp_path / "sub.unknown"
        f.write_text("1\n00:00:01,000 --> 00:00:02,000\nHello\n\n")
        assert FormatRegistry.detect_format(f) == SubtitleFormat.SRT

    def test_ass_by_magic_bytes(self, tmp_path: Path) -> None:
        f = tmp_path / "sub.unknown"
        f.write_text("[Script Info]\nTitle: Test\n\n[V4+ Styles]")
        assert FormatRegistry.detect_format(f) == SubtitleFormat.ASS

    def test_ttml_by_magic_bytes(self, tmp_path: Path) -> None:
        f = tmp_path / "sub.xml"
        f.write_text('<?xml version="1.0"?><tt xmlns="http://www.w3.org/ns/ttml">')
        assert FormatRegistry.detect_format(f) == SubtitleFormat.TTML

    def test_unknown_format(self, tmp_path: Path) -> None:
        f = tmp_path / "sub.xyz"
        f.write_text("random content here")
        assert FormatRegistry.detect_format(f) == SubtitleFormat.UNKNOWN

    def test_get_reader_raises_for_unknown(self) -> None:
        with pytest.raises(ValueError, match="No reader"):
            FormatRegistry.get_reader(SubtitleFormat.UNKNOWN)

    def test_get_writer_raises_for_bitmap_sup(self) -> None:
        with pytest.raises(ValueError, match="No writer"):
            FormatRegistry.get_writer(SubtitleFormat.SUP)

    def test_get_writer_raises_for_bitmap_sub(self) -> None:
        with pytest.raises(ValueError, match="No writer"):
            FormatRegistry.get_writer(SubtitleFormat.SUB)

    def test_supported_read_formats_includes_ttml(self) -> None:
        assert SubtitleFormat.TTML in FormatRegistry.supported_read_formats()

    def test_supported_write_formats_includes_ass(self) -> None:
        assert SubtitleFormat.ASS in FormatRegistry.supported_write_formats()

    def test_supported_write_formats_excludes_sub(self) -> None:
        assert SubtitleFormat.SUB not in FormatRegistry.supported_write_formats()
