# tests/unit/test_converter.py
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from core.translation.converter import ConversionResult, ConversionStatus, SubtitleConverter
from core.translation.models import SubtitleFormat

SRT_CONTENT = "1\n00:00:01,000 --> 00:00:03,000\nHello\n\n"


@pytest.fixture()
def srt_file(tmp_path: Path) -> Path:
    f = tmp_path / "movie.srt"
    f.write_text(SRT_CONTENT)
    return f


class TestSubtitleConverter:
    def test_srt_to_vtt(self, srt_file: Path, tmp_path: Path) -> None:
        c = SubtitleConverter()
        out = tmp_path / "movie.vtt"
        result = c.convert(srt_file, SubtitleFormat.VTT, output_path=out)
        assert result.status == ConversionStatus.SUCCESS
        assert out.exists()
        assert "WEBVTT" in out.read_text()

    def test_srt_to_ttml(self, srt_file: Path, tmp_path: Path) -> None:
        c = SubtitleConverter()
        out = tmp_path / "movie.ttml"
        result = c.convert(srt_file, SubtitleFormat.TTML, output_path=out)
        assert result.status == ConversionStatus.SUCCESS
        assert out.exists()
        assert "<tt" in out.read_text(encoding="utf-8")

    def test_srt_to_ass(self, srt_file: Path, tmp_path: Path) -> None:
        c = SubtitleConverter()
        out = tmp_path / "movie.ass"
        result = c.convert(srt_file, SubtitleFormat.ASS, output_path=out)
        assert result.status == ConversionStatus.SUCCESS
        assert "[Script Info]" in out.read_text()

    def test_srt_to_lrc(self, srt_file: Path, tmp_path: Path) -> None:
        c = SubtitleConverter()
        out = tmp_path / "movie.lrc"
        result = c.convert(srt_file, SubtitleFormat.LRC, output_path=out)
        assert result.status == ConversionStatus.SUCCESS
        assert out.exists()

    def test_srt_to_sbv(self, srt_file: Path, tmp_path: Path) -> None:
        c = SubtitleConverter()
        out = tmp_path / "movie.sbv"
        result = c.convert(srt_file, SubtitleFormat.SBV, output_path=out)
        assert result.status == ConversionStatus.SUCCESS
        assert out.exists()

    def test_srt_to_scc(self, srt_file: Path, tmp_path: Path) -> None:
        c = SubtitleConverter()
        out = tmp_path / "movie.scc"
        result = c.convert(srt_file, SubtitleFormat.SCC, output_path=out)
        assert result.status == ConversionStatus.SUCCESS

    def test_srt_to_stl(self, srt_file: Path, tmp_path: Path) -> None:
        c = SubtitleConverter()
        out = tmp_path / "movie.stl"
        result = c.convert(srt_file, SubtitleFormat.STL, output_path=out)
        assert result.status == ConversionStatus.SUCCESS

    def test_same_format_skipped(self, srt_file: Path) -> None:
        c = SubtitleConverter()
        result = c.convert(srt_file, SubtitleFormat.SRT)
        assert result.status == ConversionStatus.SKIPPED
        assert result.source_format == SubtitleFormat.SRT

    def test_missing_file_fails(self, tmp_path: Path) -> None:
        c = SubtitleConverter()
        result = c.convert(tmp_path / "ghost.srt", SubtitleFormat.VTT)
        assert result.status == ConversionStatus.FAILED
        assert result.error_message is not None

    def test_bitmap_format_fails_with_message(self, tmp_path: Path) -> None:
        f = tmp_path / "subs.sup"
        f.write_bytes(b"PG\x00" * 10)
        c = SubtitleConverter()
        result = c.convert(f, SubtitleFormat.SRT)
        assert result.status == ConversionStatus.FAILED
        assert "Bitmap" in (result.error_message or "")

    def test_dry_run_no_file_created(self, srt_file: Path, tmp_path: Path) -> None:
        c = SubtitleConverter()
        out = tmp_path / "output.vtt"
        result = c.convert(srt_file, SubtitleFormat.VTT, output_path=out, dry_run=True)
        assert result.status == ConversionStatus.SKIPPED
        assert not out.exists()

    def test_overwrite_false_skips_existing(self, srt_file: Path, tmp_path: Path) -> None:
        c = SubtitleConverter()
        out = tmp_path / "movie.vtt"
        out.write_text("existing content")
        result = c.convert(srt_file, SubtitleFormat.VTT, output_path=out, overwrite=False)
        assert result.status == ConversionStatus.SKIPPED
        assert out.read_text() == "existing content"

    def test_overwrite_true_replaces_file(self, srt_file: Path, tmp_path: Path) -> None:
        c = SubtitleConverter()
        out = tmp_path / "movie.vtt"
        out.write_text("old content")
        result = c.convert(srt_file, SubtitleFormat.VTT, output_path=out, overwrite=True)
        assert result.status == ConversionStatus.SUCCESS
        assert "WEBVTT" in out.read_text()

    def test_batch_converts_all(self, tmp_path: Path) -> None:
        files = []
        for i in range(3):
            f = tmp_path / f"sub{i}.srt"
            f.write_text(SRT_CONTENT)
            files.append(f)
        c = SubtitleConverter()
        results = c.convert_batch(files, SubtitleFormat.VTT, output_dir=tmp_path)
        assert len(results) == 3
        assert all(r.status == ConversionStatus.SUCCESS for r in results)

    def test_default_output_path(self) -> None:
        out = SubtitleConverter._default_output(Path("movie.srt"), SubtitleFormat.VTT)
        assert out == Path("movie.vtt")

    def test_default_output_ttml(self) -> None:
        out = SubtitleConverter._default_output(Path("sub.ass"), SubtitleFormat.TTML)
        assert out == Path("sub.ttml")

    def test_result_segments_count(self, srt_file: Path, tmp_path: Path) -> None:
        c = SubtitleConverter()
        out = tmp_path / "movie.vtt"
        result = c.convert(srt_file, SubtitleFormat.VTT, output_path=out)
        assert result.segments_converted == 1

    def test_result_has_source_and_target_format(self, srt_file: Path, tmp_path: Path) -> None:
        c = SubtitleConverter()
        out = tmp_path / "movie.vtt"
        result = c.convert(srt_file, SubtitleFormat.VTT, output_path=out)
        assert result.source_format == SubtitleFormat.SRT
        assert result.target_format == SubtitleFormat.VTT

    def test_unknown_format_fails(self, tmp_path: Path) -> None:
        f = tmp_path / "weird.xyz"
        f.write_text("random noise content here")
        c = SubtitleConverter()
        result = c.convert(f, SubtitleFormat.SRT)
        assert result.status == ConversionStatus.FAILED

    def test_dfxp_alias_resolved_to_ttml(self, srt_file: Path, tmp_path: Path) -> None:
        c = SubtitleConverter()
        result = c.convert(srt_file, SubtitleFormat.DFXP)
        # DFXP → resolves to TTML writer, output gets .ttml extension
        assert result.status == ConversionStatus.SUCCESS
        assert result.target_format == SubtitleFormat.TTML
