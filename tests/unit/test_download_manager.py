"""Unit tests for DownloadManager with mocked runner."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from core.download.download_manager import DownloadManager
from core.download.models import DownloadRequest, DownloadStatus, MediaType


def _raw_info(**kwargs: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "title": "Test Video",
        "uploader": "Test Channel",
        "duration": 120.0,
        "webpage_url": "https://example.com",
        "formats": [],
        "thumbnail": None,
    }
    return {**base, **kwargs}


@pytest.fixture()
def mock_runner() -> MagicMock:
    runner = MagicMock()
    runner.extract_info.return_value = _raw_info()
    runner.download.return_value = Path("out")
    return runner


@pytest.fixture()
def manager(mock_runner: MagicMock) -> DownloadManager:
    return DownloadManager(runner=mock_runner)


class TestDownloadManager:
    def test_successful_download(self, manager: DownloadManager, mock_runner: MagicMock, tmp_path: Path) -> None:
        request = DownloadRequest(
            url="https://example.com/video",
            media_type=MediaType.VIDEO,
            output_dir=tmp_path,
        )
        result = manager.download(request)

        assert result.status == DownloadStatus.SUCCESS
        mock_runner.extract_info.assert_called_once_with("https://example.com/video", download=False)
        mock_runner.download.assert_called_once()

    def test_dry_run_skips_download(self, manager: DownloadManager, mock_runner: MagicMock, tmp_path: Path) -> None:
        request = DownloadRequest(
            url="https://example.com/video",
            media_type=MediaType.VIDEO,
            output_dir=tmp_path,
            dry_run=True,
        )
        result = manager.download(request)

        assert result.status == DownloadStatus.SKIPPED
        assert result.skipped_reason == "dry_run"
        mock_runner.download.assert_not_called()

    def test_failure_returns_error(self, manager: DownloadManager, mock_runner: MagicMock, tmp_path: Path) -> None:
        mock_runner.extract_info.side_effect = RuntimeError("connection refused")
        request = DownloadRequest(
            url="https://example.com/video",
            media_type=MediaType.VIDEO,
            output_dir=tmp_path,
        )
        result = manager.download(request)

        assert result.status == DownloadStatus.FAILED
        assert "connection refused" in (result.error_message or "")

    def test_batch_download(self, manager: DownloadManager, tmp_path: Path) -> None:
        requests = [
            DownloadRequest(
                url=f"https://example.com/video{i}",
                media_type=MediaType.VIDEO,
                output_dir=tmp_path,
            )
            for i in range(3)
        ]
        results = manager.download_batch(requests)
        assert len(results) == 3
        assert all(item.status == DownloadStatus.SUCCESS for item in results)

    def test_music_request_sets_bestaudio(
        self, manager: DownloadManager, mock_runner: MagicMock, tmp_path: Path
    ) -> None:
        request = DownloadRequest(
            url="https://soundcloud.com/track",
            media_type=MediaType.MUSIC,
            output_dir=tmp_path,
        )
        manager.download(request)

        call = mock_runner.download.call_args
        enriched_request: DownloadRequest = call[0][0]
        fmt = enriched_request.extra_yt_dlp_opts.get("format", "")
        assert "bestaudio" in str(fmt)

    def test_series_request_sets_outtmpl(
        self, manager: DownloadManager, mock_runner: MagicMock, tmp_path: Path
    ) -> None:
        mock_runner.extract_info.return_value = _raw_info(series="My Show", season_number=1, episode_number=3)
        request = DownloadRequest(
            url="https://example.com/episode",
            media_type=MediaType.SERIES,
            output_dir=tmp_path,
        )
        manager.download(request)

        mock_runner.extract_info.assert_called_once_with(
            "https://example.com/episode",
            download=False,
            extra_opts={"extract_flat": "in_playlist", "ignoreerrors": True},
        )
        call = mock_runner.download.call_args
        enriched_request: DownloadRequest = call[0][0]
        outtmpl = enriched_request.extra_yt_dlp_opts.get("outtmpl", "")
        assert "Season" in str(outtmpl)
        assert enriched_request.extra_yt_dlp_opts.get("ignoreerrors") is True

    def test_youtube_playlist_enables_gentle_request_pacing(
        self, manager: DownloadManager, mock_runner: MagicMock, tmp_path: Path
    ) -> None:
        request = DownloadRequest(
            url="https://www.youtube.com/playlist?list=PL123",
            media_type=MediaType.SERIES,
            output_dir=tmp_path,
        )

        manager.download(request)

        enriched_request: DownloadRequest = mock_runner.download.call_args[0][0]
        assert enriched_request.extra_yt_dlp_opts.get("sleep_interval") == 5
        assert enriched_request.extra_yt_dlp_opts.get("max_sleep_interval") == 10
        assert enriched_request.extra_yt_dlp_opts.get("sleep_interval_requests") == 1

    def test_youtube_po_token_provider_settings_are_forwarded(
        self, manager: DownloadManager, mock_runner: MagicMock, tmp_path: Path
    ) -> None:
        request = DownloadRequest(
            url="https://www.youtube.com/watch?v=abc123",
            media_type=MediaType.VIDEO,
            output_dir=tmp_path,
            youtube_use_po_token_provider=True,
        )

        manager.download(request)

        enriched_request: DownloadRequest = mock_runner.download.call_args[0][0]
        extractor_args = enriched_request.extra_yt_dlp_opts.get("extractor_args")
        assert isinstance(extractor_args, dict)
        youtube_args = extractor_args.get("youtube")
        assert isinstance(youtube_args, dict)
        assert youtube_args.get("player_client") == ["mweb"]
        assert youtube_args.get("fetch_pot") == ["always"]

    def test_manual_youtube_po_token_is_normalized(
        self, manager: DownloadManager, mock_runner: MagicMock, tmp_path: Path
    ) -> None:
        request = DownloadRequest(
            url="https://www.youtube.com/watch?v=abc123",
            media_type=MediaType.VIDEO,
            output_dir=tmp_path,
            youtube_player_client="mweb",
            youtube_po_token="TOKEN123",
        )

        manager.download(request)

        enriched_request: DownloadRequest = mock_runner.download.call_args[0][0]
        extractor_args = enriched_request.extra_yt_dlp_opts.get("extractor_args")
        assert isinstance(extractor_args, dict)
        youtube_args = extractor_args.get("youtube")
        assert isinstance(youtube_args, dict)
        assert youtube_args.get("po_token") == ["mweb.gvs+TOKEN123"]

    def test_auth_error_retries_with_browser_cookies(
        self, manager: DownloadManager, mock_runner: MagicMock, tmp_path: Path
    ) -> None:
        mock_runner.download.side_effect = [
            RuntimeError("Login required to access this resource"),
            Path("out"),
        ]
        request = DownloadRequest(
            url="https://example.com/protected",
            media_type=MediaType.VIDEO,
            output_dir=tmp_path,
        )

        result = manager.download(request)

        assert result.status == DownloadStatus.SUCCESS
        assert mock_runner.download.call_count == 2
        retried_request: DownloadRequest = mock_runner.download.call_args_list[1][0][0]
        assert retried_request.cookies_from_browser == "chrome"

    def test_auth_error_no_retry_when_cookie_already_supplied(
        self, manager: DownloadManager, mock_runner: MagicMock, tmp_path: Path
    ) -> None:
        mock_runner.download.side_effect = RuntimeError("Login required")
        request = DownloadRequest(
            url="https://example.com/protected",
            media_type=MediaType.VIDEO,
            output_dir=tmp_path,
            cookies_from_browser="firefox",
        )

        result = manager.download(request)

        assert result.status == DownloadStatus.FAILED
        assert mock_runner.download.call_count == 1

    def test_music_set_uses_playlist_tolerant_mode(
        self, manager: DownloadManager, mock_runner: MagicMock, tmp_path: Path
    ) -> None:
        request = DownloadRequest(
            url="https://soundcloud.com/example/sets/mix",
            media_type=MediaType.MUSIC,
            output_dir=tmp_path,
        )

        manager.download(request)

        mock_runner.extract_info.assert_called_once_with(
            "https://soundcloud.com/example/sets/mix",
            download=False,
            extra_opts={"extract_flat": "in_playlist", "ignoreerrors": True},
        )

    def test_geo_restriction_error_is_user_friendly(
        self, manager: DownloadManager, mock_runner: MagicMock, tmp_path: Path
    ) -> None:
        mock_runner.extract_info.side_effect = RuntimeError(
            "ERROR: [soundcloud] This video is not available from your location due to geo restriction"
        )
        request = DownloadRequest(
            url="https://soundcloud.com/example/set",
            media_type=MediaType.MUSIC,
            output_dir=tmp_path,
        )

        result = manager.download(request)

        assert result.status == DownloadStatus.FAILED
        assert result.error_message is not None
        assert "Geo-restricted" in result.error_message
        assert "VPN" in result.error_message

    def test_auth_error_message_suggests_cookie_options(
        self, manager: DownloadManager, mock_runner: MagicMock, tmp_path: Path
    ) -> None:
        mock_runner.download.side_effect = RuntimeError("Sign in to confirm your age")
        request = DownloadRequest(
            url="https://example.com/protected",
            media_type=MediaType.VIDEO,
            output_dir=tmp_path,
            cookies_from_browser="firefox",
        )

        result = manager.download(request)

        assert result.status == DownloadStatus.FAILED
        assert result.error_message is not None
        assert "authentication" in result.error_message.lower()
        assert "cookies-from-browser" in result.error_message

    def test_stale_youtube_cookie_error_suggests_fresh_export_steps(
        self, manager: DownloadManager, mock_runner: MagicMock, tmp_path: Path
    ) -> None:
        mock_runner.download.side_effect = RuntimeError(
            "yt-dlp reported download errors and no files were saved "
            "(Last reported issue: [youtube:tab] The provided YouTube account cookies are no longer valid. "
            "They have likely been rotated in the browser as a security measure.)"
        )
        request = DownloadRequest(
            url="https://youtube.com/playlist?list=PL123",
            media_type=MediaType.SERIES,
            output_dir=tmp_path,
        )

        result = manager.download(request)

        assert result.status == DownloadStatus.FAILED
        assert result.error_message is not None
        assert "private/incognito" in result.error_message
        assert "robots.txt" in result.error_message
        assert "--cookies-file" in result.error_message

    def test_youtube_rate_limit_error_is_actionable(
        self, manager: DownloadManager, mock_runner: MagicMock, tmp_path: Path
    ) -> None:
        mock_runner.download.side_effect = RuntimeError(
            "yt-dlp reported download errors and no files were saved "
            "(Last reported issue: ERROR: [youtube] dGw3w_njQ4g: Video unavailable. "
            "This content isn't available, try again later. The current session has been rate-limited by YouTube for up to an hour.)"
        )
        request = DownloadRequest(
            url="https://youtube.com/playlist?list=PL123",
            media_type=MediaType.SERIES,
            output_dir=tmp_path,
        )

        result = manager.download(request)

        assert result.status == DownloadStatus.FAILED
        assert result.error_message is not None
        assert "rate-limited" in result.error_message
        assert "Wait up to an hour" in result.error_message
        assert "--cookies-file" in result.error_message
        assert "--youtube-use-po-token-provider" in result.error_message

    def test_missing_po_token_error_is_actionable(
        self, manager: DownloadManager, mock_runner: MagicMock, tmp_path: Path
    ) -> None:
        mock_runner.download.side_effect = RuntimeError(
            "abc123: mweb client https formats require a GVS PO Token which was not provided"
        )
        request = DownloadRequest(
            url="https://youtube.com/watch?v=abc123",
            media_type=MediaType.VIDEO,
            output_dir=tmp_path,
        )

        result = manager.download(request)

        assert result.status == DownloadStatus.FAILED
        assert result.error_message is not None
        assert "PO Token" in result.error_message
        assert "--youtube-use-po-token-provider" in result.error_message
        assert "--youtube-po-token" in result.error_message

    def test_youtube_country_block_error_is_user_friendly(
        self, manager: DownloadManager, mock_runner: MagicMock, tmp_path: Path
    ) -> None:
        mock_runner.extract_info.side_effect = RuntimeError(
            "ERROR: [youtube] abc123: The uploader has not made this video available in your country"
        )
        request = DownloadRequest(
            url="https://youtube.com/watch?v=abc123",
            media_type=MediaType.VIDEO,
            output_dir=tmp_path,
        )

        result = manager.download(request)

        assert result.status == DownloadStatus.FAILED
        assert result.error_message is not None
        assert result.error_message.startswith("Geo-restricted content:")

    def test_playlist_download_logs_summary(
        self,
        manager: DownloadManager,
        mock_runner: MagicMock,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        mock_runner.extract_info.return_value = {
            **_raw_info(title="My Playlist"),
            "entries": [
                {"id": "1", "title": "Song A", "channel": "Artist A"},
                {"id": "2", "title": "Song B"},
                None,
            ],
        }
        request = DownloadRequest(
            url="https://youtube.com/watch?v=abc123&list=PL123",
            media_type=MediaType.SERIES,
            output_dir=tmp_path,
        )

        with caplog.at_level(logging.WARNING):
            result = manager.download(request)

        assert result.status == DownloadStatus.SUCCESS
        assert "Playlist detected: My Playlist (2 available / 3 total entries)" in caplog.text
        assert "Playlist item 1/3: Song A — Artist A" in caplog.text
        assert "Playlist item 2/3: Song B" in caplog.text
        assert "Playlist item 3/3: unavailable or hidden entry" in caplog.text
