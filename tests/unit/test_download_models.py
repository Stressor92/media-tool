"""Unit tests for download data models."""

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from core.download.models import DownloadRequest, DownloadResult, DownloadStatus, MediaType, TrackInfo


class TestDownloadRequest:
    def test_defaults(self) -> None:
        request = DownloadRequest(
            url="https://example.com/video",
            media_type=MediaType.VIDEO,
            output_dir=Path("out"),
        )
        assert request.max_resolution == 1080
        assert request.audio_format == "mp3"
        assert request.embed_subtitles is True
        assert request.sponsorblock_remove == ("sponsor",)
        assert request.cookies_from_browser is None
        assert request.cookies_file is None

    def test_cookie_fields(self) -> None:
        request = DownloadRequest(
            url="https://example.com/video",
            media_type=MediaType.VIDEO,
            output_dir=Path("out"),
            cookies_from_browser="chrome",
            cookies_file=Path("cookies.txt"),
        )
        assert request.cookies_from_browser == "chrome"
        assert request.cookies_file == Path("cookies.txt")

    def test_frozen(self) -> None:
        request = DownloadRequest(
            url="https://example.com",
            media_type=MediaType.MUSIC,
            output_dir=Path("out"),
        )
        with pytest.raises(FrozenInstanceError):
            request.url = "https://changed.example"  # type: ignore[misc]

    def test_subtitle_languages_tuple(self) -> None:
        request = DownloadRequest(
            url="https://example.com",
            media_type=MediaType.VIDEO,
            output_dir=Path("out"),
            subtitle_languages=("de", "en", "fr"),
        )
        assert isinstance(request.subtitle_languages, tuple)
        assert len(request.subtitle_languages) == 3


class TestTrackInfo:
    def test_optional_series_fields_default_none(self) -> None:
        info = TrackInfo(
            title="Video",
            uploader="Uploader",
            duration=300.0,
            url="https://example.com",
        )
        assert info.series is None
        assert info.season_number is None
        assert info.episode_number is None
        assert info.formats == []


class TestDownloadResult:
    def test_success_result(self, tmp_path: Path) -> None:
        request = DownloadRequest(
            url="https://example.com",
            media_type=MediaType.VIDEO,
            output_dir=tmp_path,
        )
        result = DownloadResult(
            status=DownloadStatus.SUCCESS,
            request=request,
            output_path=tmp_path / "video.mkv",
        )
        assert result.status == DownloadStatus.SUCCESS
        assert result.output_path is not None
        assert result.error_message is None

    def test_failed_result(self, tmp_path: Path) -> None:
        request = DownloadRequest(
            url="https://example.com",
            media_type=MediaType.VIDEO,
            output_dir=tmp_path,
        )
        result = DownloadResult(
            status=DownloadStatus.FAILED,
            request=request,
            error_message="network error",
        )
        assert result.status == DownloadStatus.FAILED
        assert result.output_path is None
