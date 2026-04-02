"""Low-level yt-dlp subprocess wrapper for trailer search and downloads."""

from __future__ import annotations

import json
import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class YtDlpError(RuntimeError):
    """Raised when yt-dlp invocation fails."""


class YtDlpNotFoundError(YtDlpError):
    """Raised when yt-dlp binary cannot be found."""


@dataclass(slots=True)
class VideoInfo:
    """Minimal metadata extracted from yt-dlp search results."""

    title: str
    url: str
    uploader: str | None = None
    duration: int | None = None
    view_count: int | None = None
    upload_date: str | None = None
    description: str | None = None
    language: str | None = None


@dataclass(slots=True)
class DownloadResult:
    """Result of a trailer download attempt."""

    success: bool
    file_path: Path | None = None
    error: str | None = None


class YtDlpRunner:
    """Execute yt-dlp as a subprocess for predictable CLI behavior."""

    def __init__(self, ytdlp_binary: str = "yt-dlp", verify_installation: bool = True) -> None:
        self.ytdlp_binary = ytdlp_binary
        if verify_installation:
            self._verify_installation()

    def _verify_installation(self) -> None:
        try:
            subprocess.run(
                [self.ytdlp_binary, "--version"],
                capture_output=True,
                text=True,
                check=True,
                timeout=10,
            )
        except FileNotFoundError as exc:
            raise YtDlpNotFoundError(f"yt-dlp executable not found: {self.ytdlp_binary}") from exc
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            raise YtDlpError(f"Failed to verify yt-dlp executable: {exc}") from exc

    def search(
        self,
        query: str,
        max_results: int = 5,
        timeout_seconds: int = 30,
    ) -> list[VideoInfo]:
        """Search YouTube and return parsed candidate videos."""
        search_query = f"ytsearch{max_results}:{query}"
        cmd = [
            self.ytdlp_binary,
            search_query,
            "--dump-json",
            "--no-playlist",
            "--skip-download",
            "--ignore-errors",
        ]

        try:
            completed = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
                timeout=timeout_seconds,
            )
        except FileNotFoundError as exc:
            raise YtDlpNotFoundError(f"yt-dlp executable not found: {self.ytdlp_binary}") from exc
        except subprocess.TimeoutExpired as exc:
            raise YtDlpError(f"yt-dlp search timed out for query '{query}'") from exc

        if completed.returncode != 0:
            stderr = completed.stderr.strip()
            raise YtDlpError(f"yt-dlp search failed for query '{query}': {stderr or 'unknown error'}")

        videos: list[VideoInfo] = []
        for line in completed.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                logger.debug("Skipping invalid yt-dlp JSON line", extra={"line": line})
                continue

            if not isinstance(payload, dict):
                continue

            video = self._parse_video_info(payload)
            if video is not None:
                videos.append(video)

        return videos

    def download(
        self,
        url: str,
        output_path: Path,
        timeout_seconds: int = 600,
    ) -> DownloadResult:
        """Download one trailer URL into a deterministic mp4 path."""
        output_path.parent.mkdir(parents=True, exist_ok=True)

        temp_template = output_path.parent / f"{output_path.stem}-%(id)s.%(ext)s"
        cmd = [
            self.ytdlp_binary,
            url,
            "--format",
            "best[ext=mp4]/best",
            "--output",
            str(temp_template),
            "--no-playlist",
            "--merge-output-format",
            "mp4",
        ]

        try:
            completed = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
                timeout=timeout_seconds,
            )
        except FileNotFoundError:
            return DownloadResult(success=False, error=f"yt-dlp not found: {self.ytdlp_binary}")
        except subprocess.TimeoutExpired:
            return DownloadResult(success=False, error="yt-dlp download timed out")

        if completed.returncode != 0:
            stderr = completed.stderr.strip()
            return DownloadResult(
                success=False,
                error=f"yt-dlp download failed: {stderr or 'unknown error'}",
            )

        pattern = f"{output_path.stem}-*.mp4"
        downloaded_files = sorted(
            output_path.parent.glob(pattern),
            key=lambda file_path: file_path.stat().st_mtime,
            reverse=True,
        )
        if not downloaded_files:
            return DownloadResult(
                success=False,
                error="yt-dlp finished without creating an mp4 output file",
            )

        temp_file = downloaded_files[0]
        try:
            if output_path.exists():
                output_path.unlink()
            temp_file.rename(output_path)
        except OSError as exc:
            return DownloadResult(success=False, error=f"Failed to finalize trailer file: {exc}")

        return DownloadResult(success=True, file_path=output_path)

    @staticmethod
    def _parse_video_info(payload: dict[str, Any]) -> VideoInfo | None:
        title = payload.get("title")
        webpage_url = payload.get("webpage_url")
        video_id = payload.get("id")

        if not isinstance(title, str):
            return None

        if isinstance(webpage_url, str) and webpage_url:
            url = webpage_url
        elif isinstance(video_id, str) and video_id:
            url = f"https://www.youtube.com/watch?v={video_id}"
        else:
            return None

        return VideoInfo(
            title=title,
            url=url,
            uploader=payload.get("uploader") if isinstance(payload.get("uploader"), str) else None,
            duration=payload.get("duration") if isinstance(payload.get("duration"), int) else None,
            view_count=payload.get("view_count") if isinstance(payload.get("view_count"), int) else None,
            upload_date=(payload.get("upload_date") if isinstance(payload.get("upload_date"), str) else None),
            description=(payload.get("description") if isinstance(payload.get("description"), str) else None),
            language=payload.get("language") if isinstance(payload.get("language"), str) else None,
        )
