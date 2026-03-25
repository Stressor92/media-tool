"""Unit tests for yt-dlp parsing helper."""

from pathlib import Path
from typing import Any

from core.download.models import DownloadRequest, MediaType
from core.download.yt_dlp_runner import YtDlpRunner
from core.download.yt_dlp_runner import parse_track_info


RAW_VIDEO: dict[str, Any] = {
    "title": "Awesome Video",
    "uploader": "Cool Channel",
    "duration": 600.5,
    "webpage_url": "https://youtube.com/watch?v=abc",
    "formats": [{"format_id": "137"}, {"format_id": "251"}],
    "thumbnail": "https://img.youtube.com/abc/default.jpg",
}

RAW_SERIES: dict[str, Any] = {
    "title": "Episode Title",
    "uploader": "TV Channel",
    "duration": 2400.0,
    "webpage_url": "https://example.com/episode",
    "series": "My Great Show",
    "season_number": 2,
    "episode_number": 5,
    "formats": [],
    "thumbnail": None,
}


class TestParseTrackInfo:
    def test_basic_video_fields(self) -> None:
        info = parse_track_info(RAW_VIDEO)
        assert info.title == "Awesome Video"
        assert info.uploader == "Cool Channel"
        assert info.duration == 600.5
        assert info.url == "https://youtube.com/watch?v=abc"
        assert info.thumbnail_url == "https://img.youtube.com/abc/default.jpg"
        assert info.formats == ["137", "251"]

    def test_series_fields(self) -> None:
        info = parse_track_info(RAW_SERIES)
        assert info.series == "My Great Show"
        assert info.season_number == 2
        assert info.episode_number == 5

    def test_missing_optional_fields(self) -> None:
        info = parse_track_info({"title": "X", "uploader": "Y", "webpage_url": ""})
        assert info.duration is None
        assert info.series is None
        assert info.formats == []

    def test_unknown_fallbacks(self) -> None:
        info = parse_track_info({})
        assert info.title == "unknown"
        assert info.uploader == "unknown"


class TestYtDlpRunnerOptions:
    def test_cookies_from_browser_passed(self) -> None:
        request = DownloadRequest(
            url="https://example.com",
            media_type=MediaType.VIDEO,
            output_dir=Path("out"),
            cookies_from_browser="chrome",
        )
        opts = YtDlpRunner()._build_opts(request)
        assert opts["cookiesfrombrowser"] == ("chrome",)

    def test_cookie_file_passed(self) -> None:
        request = DownloadRequest(
            url="https://example.com",
            media_type=MediaType.VIDEO,
            output_dir=Path("out"),
            cookies_file=Path("cookies.txt"),
        )
        opts = YtDlpRunner()._build_opts(request)
        assert opts["cookiefile"] == "cookies.txt"
