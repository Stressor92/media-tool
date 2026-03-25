"""Integration tests for yt-dlp download workflow."""

from __future__ import annotations

from pathlib import Path

import pytest

from core.download.download_manager import DownloadManager
from core.download.models import DownloadRequest, DownloadStatus, MediaType

TEST_VIDEO_URL = "https://www.youtube.com/watch?v=jNQXAC9IVRw"


@pytest.mark.integration
class TestDownloadIntegration:
    def test_video_dry_run_returns_track_info(self, tmp_path: Path) -> None:
        request = DownloadRequest(
            url=TEST_VIDEO_URL,
            media_type=MediaType.VIDEO,
            output_dir=tmp_path,
            dry_run=True,
        )
        result = DownloadManager().download(request)

        assert result.status == DownloadStatus.SKIPPED
        assert result.track_info is not None
        assert result.track_info.title != ""
        assert not any(tmp_path.rglob("*"))

    def test_invalid_url_fails(self, tmp_path: Path) -> None:
        request = DownloadRequest(
            url="https://www.youtube.com/watch?v=INVALID_ID_XYZ",
            media_type=MediaType.VIDEO,
            output_dir=tmp_path,
        )
        result = DownloadManager().download(request)

        assert result.status == DownloadStatus.FAILED
        assert result.error_message is not None
