"""Unit tests for DownloadManager with mocked runner."""

from __future__ import annotations

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

        call = mock_runner.download.call_args
        enriched_request: DownloadRequest = call[0][0]
        outtmpl = enriched_request.extra_yt_dlp_opts.get("outtmpl", "")
        assert "Season" in str(outtmpl)

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
