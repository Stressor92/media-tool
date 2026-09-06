from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Literal
from unittest.mock import patch

import pytest

from core.download.models import DownloadRequest, MediaType
from core.download.yt_dlp_runner import YtDlpRunner


def test_series_download_allows_partial_playlist_success(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    request = DownloadRequest(
        url="https://example.com/playlist",
        media_type=MediaType.SERIES,
        output_dir=tmp_path,
        extra_yt_dlp_opts={"ignoreerrors": True},
        expected_playlist_items=3,
    )

    created_file = tmp_path / "Episode 01.mp4"
    captured_opts: list[dict[str, Any]] = []

    class _FakeYoutubeDL:
        def __init__(self, opts: dict[str, Any]) -> None:
            self._opts = opts
            captured_opts.append(opts)

        def __enter__(self) -> _FakeYoutubeDL:
            return self

        def __exit__(self, exc_type: object, exc: object, tb: object) -> Literal[False]:
            return False

        def download(self, urls: list[str]) -> int:
            del urls
            info = {"title": "Episode 01", "playlist_index": 1, "n_entries": 3, "id": "ep1"}
            for hook in self._opts["progress_hooks"]:
                hook({"status": "downloading", "filename": str(created_file), "info_dict": info})
                hook({"status": "finished", "filename": str(created_file), "info_dict": info})
            created_file.write_text("video", encoding="utf-8")
            return 1

    with patch("core.download.yt_dlp_runner.yt_dlp.YoutubeDL", _FakeYoutubeDL):
        runner = YtDlpRunner()
        with caplog.at_level(logging.WARNING):
            result = runner.download(request)

    assert result == tmp_path
    assert captured_opts
    assert captured_opts[0]["ignoreerrors"] is True
    assert "saved 1 of 3 queued item(s)" in caplog.text
    assert "2 item(s) never reached the actual download stage" in caplog.text


def test_series_download_raises_when_every_item_fails(tmp_path: Path) -> None:
    request = DownloadRequest(
        url="https://example.com/playlist",
        media_type=MediaType.SERIES,
        output_dir=tmp_path,
        extra_yt_dlp_opts={"ignoreerrors": True},
    )

    class _FakeYoutubeDL:
        def __init__(self, opts: dict[str, Any]) -> None:
            del opts

        def __enter__(self) -> _FakeYoutubeDL:
            return self

        def __exit__(self, exc_type: object, exc: object, tb: object) -> Literal[False]:
            return False

        def download(self, urls: list[str]) -> int:
            del urls
            return 1

    with patch("core.download.yt_dlp_runner.yt_dlp.YoutubeDL", _FakeYoutubeDL):
        runner = YtDlpRunner()
        with pytest.raises(RuntimeError, match="no files were saved"):
            runner.download(request)


def test_series_download_thumbnail_only_artifacts_do_not_count_as_saved(tmp_path: Path) -> None:
    request = DownloadRequest(
        url="https://example.com/playlist",
        media_type=MediaType.SERIES,
        output_dir=tmp_path,
        extra_yt_dlp_opts={"ignoreerrors": True},
        extract_audio=True,
    )

    class _FakeYoutubeDL:
        def __init__(self, opts: dict[str, Any]) -> None:
            del opts

        def __enter__(self) -> _FakeYoutubeDL:
            return self

        def __exit__(self, exc_type: object, exc: object, tb: object) -> Literal[False]:
            return False

        def download(self, urls: list[str]) -> int:
            del urls
            (tmp_path / "cover.jpg").write_text("thumbnail", encoding="utf-8")
            return 1

    with patch("core.download.yt_dlp_runner.yt_dlp.YoutubeDL", _FakeYoutubeDL):
        runner = YtDlpRunner()
        with pytest.raises(RuntimeError, match="Only non-media helper files were created"):
            runner.download(request)


def test_series_download_logs_item_progress(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    request = DownloadRequest(
        url="https://example.com/playlist",
        media_type=MediaType.SERIES,
        output_dir=tmp_path,
        extra_yt_dlp_opts={"ignoreerrors": True},
    )

    class _FakeYoutubeDL:
        def __init__(self, opts: dict[str, Any]) -> None:
            self._opts = opts

        def __enter__(self) -> _FakeYoutubeDL:
            return self

        def __exit__(self, exc_type: object, exc: object, tb: object) -> Literal[False]:
            return False

        def download(self, urls: list[str]) -> int:
            del urls
            hooks = self._opts["progress_hooks"]
            info = {
                "title": "Episode One",
                "playlist_index": 1,
                "n_entries": 3,
                "playlist_count": 3,
                "id": "ep1",
            }
            for hook in hooks:
                hook({"status": "downloading", "filename": str(tmp_path / "ep1.mp4"), "info_dict": {}})
                hook({"status": "finished", "filename": str(tmp_path / "ep1.mp4"), "info_dict": {}})
                hook({"status": "downloading", "filename": str(tmp_path / "ep1.mp4"), "info_dict": info})
                hook({"status": "finished", "filename": str(tmp_path / "ep1.mp4"), "info_dict": info})
            (tmp_path / "ep1.mp4").write_text("video", encoding="utf-8")
            return 0

    with patch("core.download.yt_dlp_runner.yt_dlp.YoutubeDL", _FakeYoutubeDL):
        runner = YtDlpRunner()
        with caplog.at_level(logging.WARNING):
            runner.download(request)

    assert "Downloading item 1/3: Episode One" in caplog.text
    assert "Finished item 1/3: Episode One" in caplog.text
    assert "Downloading item: unknown" not in caplog.text


def test_series_download_failure_includes_last_reported_issue(tmp_path: Path) -> None:
    request = DownloadRequest(
        url="https://example.com/playlist",
        media_type=MediaType.SERIES,
        output_dir=tmp_path,
        extra_yt_dlp_opts={"ignoreerrors": True},
    )

    class _FakeYoutubeDL:
        def __init__(self, opts: dict[str, Any]) -> None:
            self._opts = opts

        def __enter__(self) -> _FakeYoutubeDL:
            return self

        def __exit__(self, exc_type: object, exc: object, tb: object) -> Literal[False]:
            return False

        def download(self, urls: list[str]) -> int:
            del urls
            self._opts["logger"].warning("[youtube] No title found in player responses")
            self._opts["logger"].error(
                "ERROR: [youtube] abc123: The uploader has not made this video available in your country"
            )
            return 1

    with patch("core.download.yt_dlp_runner.yt_dlp.YoutubeDL", _FakeYoutubeDL):
        runner = YtDlpRunner()
        with pytest.raises(RuntimeError, match="Last reported issue") as exc_info:
            runner.download(request)

    assert "available in your country" in str(exc_info.value)


def test_logger_normalizes_and_deduplicates_signature_challenge_warnings(
    caplog: pytest.LogCaptureFixture,
) -> None:
    runner = YtDlpRunner()

    with caplog.at_level(logging.WARNING):
        runner._yt_logger.warning("[youtube] id-a: Signature solving failed")
        runner._yt_logger.warning("[youtube] id-b: Signature solving failed")

    expected = "YouTube signature/challenge solving failed; some formats may be missing"
    assert caplog.text.count(expected) == 1
