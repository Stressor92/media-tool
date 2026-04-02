from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

import yt_dlp

from core.download.models import DownloadRequest, TrackInfo

logger = logging.getLogger(__name__)


@runtime_checkable
class YtDlpRunnerProtocol(Protocol):
    """Protocol for yt-dlp access used by DownloadManager."""

    def extract_info(self, url: str, *, download: bool = False) -> dict[str, Any]:
        """Fetch metadata for a URL."""

    def download(self, request: DownloadRequest) -> Path:
        """Download media and return output directory path."""


class YtDlpRunner:
    """Thin wrapper around yt-dlp's Python API."""

    def __init__(self, base_opts: dict[str, Any] | None = None) -> None:
        self._base_opts: dict[str, Any] = base_opts or {}

    def _build_opts(self, request: DownloadRequest) -> dict[str, Any]:
        outtmpl = str(request.output_dir / "%(uploader)s/%(title)s.%(ext)s")
        opts: dict[str, Any] = {
            **self._base_opts,
            "outtmpl": outtmpl,
            "overwrites": request.overwrite,
            "quiet": True,
            "no_warnings": False,
            **request.extra_yt_dlp_opts,
        }

        if request.cookies_from_browser:
            opts["cookiesfrombrowser"] = (request.cookies_from_browser,)

        if request.cookies_file is not None:
            opts["cookiefile"] = str(request.cookies_file)

        return opts

    def extract_info(self, url: str, *, download: bool = False) -> dict[str, Any]:
        with yt_dlp.YoutubeDL({"quiet": True}) as ydl:
            info: dict[str, Any] = ydl.extract_info(url, download=download)
            return info

    def download(self, request: DownloadRequest) -> Path:
        request.output_dir.mkdir(parents=True, exist_ok=True)
        opts = self._build_opts(request)
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([request.url])
        return request.output_dir


def parse_track_info(raw: dict[str, Any]) -> TrackInfo:
    """Convert raw yt-dlp info dictionary into typed TrackInfo."""
    raw_formats = raw.get("formats", [])
    format_ids: list[str] = []
    if isinstance(raw_formats, list):
        for item in raw_formats:
            if isinstance(item, dict):
                format_id = item.get("format_id")
                if format_id is not None:
                    format_ids.append(str(format_id))

    return TrackInfo(
        title=str(raw.get("title", "unknown")),
        uploader=str(raw.get("uploader", "unknown")),
        duration=float(raw["duration"]) if isinstance(raw.get("duration"), int | float) else None,
        url=str(raw.get("webpage_url", "")),
        playlist_index=int(raw["playlist_index"]) if isinstance(raw.get("playlist_index"), int) else None,
        series=str(raw["series"]) if isinstance(raw.get("series"), str) else None,
        season_number=int(raw["season_number"]) if isinstance(raw.get("season_number"), int) else None,
        episode_number=int(raw["episode_number"]) if isinstance(raw.get("episode_number"), int) else None,
        thumbnail_url=str(raw["thumbnail"]) if isinstance(raw.get("thumbnail"), str) else None,
        formats=format_ids,
    )
