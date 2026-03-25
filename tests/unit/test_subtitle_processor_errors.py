"""Error-path tests aligned with the current subtitle processing APIs."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from core.subtitles.subtitle_downloader import SubtitleDownloadManager
from core.subtitles.subtitle_provider import DownloadResult, SubtitleProvider
from core.video.subtitle_processor import SubtitleTimingProcessor


class TestSubtitleDownloadManagerErrors:
    def test_process_missing_video_raises(self, tmp_path: Path) -> None:
        provider = MagicMock(spec=SubtitleProvider)
        manager = SubtitleDownloadManager(provider, MagicMock())

        with pytest.raises(FileNotFoundError):
            manager.process(tmp_path / "missing.mkv")

    def test_process_no_results_returns_fallback(self, tmp_path: Path) -> None:
        provider = MagicMock(spec=SubtitleProvider)
        provider.search.return_value = []
        manager = SubtitleDownloadManager(provider, MagicMock())
        video = tmp_path / "movie.mkv"
        video.touch()

        manager_any: Any = manager
        manager_any._should_process_file = MagicMock(return_value=True)
        manager_any._extract_movie_info = MagicMock()

        result = manager.process(video)

        assert isinstance(result, DownloadResult)
        assert result.success is False
        assert result.fallback_suggestion == "whisper"

    def test_process_download_error_returns_failure(self, tmp_path: Path) -> None:
        provider = MagicMock(spec=SubtitleProvider)
        match = MagicMock(format="srt", language="en")
        provider.search.return_value = [match]
        provider.get_best_match.return_value = match
        manager = SubtitleDownloadManager(provider, MagicMock())
        video = tmp_path / "movie.mkv"
        video.touch()

        manager_any: Any = manager
        manager_any._should_process_file = MagicMock(return_value=True)
        manager_any._extract_movie_info = MagicMock()
        manager_any._download_subtitle = MagicMock(side_effect=RuntimeError("download failed"))

        result = manager.process(video)

        assert result.success is False
        assert "Download failed" in result.message


class TestSubtitleValidationErrors:
    def test_validate_srt_utf8_valid(self, tmp_path: Path) -> None:
        srt_path = tmp_path / "utf8.srt"
        srt_path.write_text(
            "1\n00:00:00,000 --> 00:00:05,000\nText with Unicode: © € ñ é\n",
            encoding="utf-8",
        )

        result = SubtitleTimingProcessor().validate_srt(srt_path)
        assert result.is_valid

    def test_validate_srt_bom_valid(self, tmp_path: Path) -> None:
        srt_path = tmp_path / "bom.srt"
        srt_path.write_bytes(
            b"\xef\xbb\xbf1\n00:00:00,000 --> 00:00:05,000\nText content\n"
        )

        result = SubtitleTimingProcessor().validate_srt(srt_path)
        assert result.is_valid

    def test_validate_srt_invalid_utf8(self, tmp_path: Path) -> None:
        srt_path = tmp_path / "bad.srt"
        srt_path.write_bytes(b"1\n00:00:00,000 --> 00:00:05,000\nBad \x80\x81 bytes\n")

        result = SubtitleTimingProcessor().validate_srt(srt_path)
        assert result.is_valid is False
        assert result.errors

    def test_validate_unicode_heavy_subtitles(self, tmp_path: Path) -> None:
        srt_path = tmp_path / "unicode_heavy.srt"
        srt_path.write_text(
            "1\n00:00:00,000 --> 00:00:05,000\nHello 你好 مرحبا שלום привет\n\n"
            "2\n00:00:05,000 --> 00:00:10,000\n🎬 🎥 🎞️ 📹 🎭\n",
            encoding="utf-8",
        )

        result = SubtitleTimingProcessor().validate_srt(srt_path)
        assert result.is_valid

