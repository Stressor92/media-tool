"""Integration tests for yt-dlp download workflow with mocked runner."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from core.download.download_manager import DownloadManager
from core.download.models import DownloadRequest, DownloadStatus, MediaType


def _mock_info(**kwargs: Any) -> dict[str, Any]:
    """Create mock track info matching real yt-dlp responses."""
    base: dict[str, Any] = {
        "title": "Test Video",
        "uploader": "Test Channel",
        "duration": 120.0,
        "webpage_url": "https://example.com",
        "formats": [],
        "thumbnail": None,
    }
    return {**base, **kwargs}


@pytest.fixture
def mock_runner() -> MagicMock:
    """Mock yt-dlp runner to avoid real API calls."""
    runner = MagicMock()
    runner.extract_info.return_value = _mock_info()
    runner.download.return_value = Path("test_video.mp4")
    return runner


@pytest.fixture
def mock_manager(mock_runner: MagicMock) -> DownloadManager:
    """Create DownloadManager with mocked runner."""
    return DownloadManager(runner=mock_runner)


@pytest.mark.integration
class TestDownloadIntegration:
    def test_video_dry_run_returns_track_info(self, tmp_path: Path, mock_manager: DownloadManager, mock_runner: MagicMock) -> None:
        """Test that dry run returns info without downloading."""
        request = DownloadRequest(
            url="https://example.com/video",
            media_type=MediaType.VIDEO,
            output_dir=tmp_path,
            dry_run=True,
        )
        result = mock_manager.download(request)

        # Verify extract_info was called (for dry run)
        mock_runner.extract_info.assert_called_once()
        # Verify download was not called
        mock_runner.download.assert_not_called()
        # Verify result
        assert result.status == DownloadStatus.SKIPPED
        assert result.track_info is not None
        assert result.track_info.title == "Test Video"

    def test_invalid_url_fails(self, tmp_path: Path, mock_manager: DownloadManager, mock_runner: MagicMock) -> None:
        """Test that invalid URLs are handled gracefully."""
        # Mock runner to raise exception for invalid URLs
        mock_runner.extract_info.side_effect = Exception("Video unavailable")
        
        request = DownloadRequest(
            url="https://example.com/invalid",
            media_type=MediaType.VIDEO,
            output_dir=tmp_path,
        )
        result = mock_manager.download(request)

        assert result.status == DownloadStatus.FAILED
        assert result.error_message is not None
