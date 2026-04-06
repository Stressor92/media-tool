from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

import yt_dlp

from core.download.models import DownloadRequest, TrackInfo

logger = logging.getLogger(__name__)


class _YtDlpLogger:
    """Bridge yt-dlp messages into the app logger without noisy stderr output."""

    def __init__(self, remember_issue: Callable[[str], None] | None = None) -> None:
        self._seen_warnings: set[str] = set()
        self._remember_issue = remember_issue

    @staticmethod
    def _normalize(message: str) -> str:
        return " ".join(message.split())

    def debug(self, message: str) -> None:
        logger.debug("yt-dlp: %s", self._normalize(message))

    def warning(self, message: str) -> None:
        normalized = self._normalize(message)
        if "No supported JavaScript runtime could be found" in normalized:
            normalized = (
                "YouTube extraction is running without a JavaScript runtime; some formats may be missing. "
                "Install Deno/Node.js or configure yt-dlp js runtimes for best compatibility."
            )
        elif "The extractor specified to use impersonation for this download" in normalized:
            normalized = (
                "The site requested yt-dlp impersonation support, but no impersonation backend is installed. "
                "Some downloads may fail until the optional dependency is configured."
            )
        elif "The provided YouTube account cookies are no longer valid" in normalized:
            normalized = (
                "YouTube cookies from the browser look stale or rotated. "
                "Create a fresh private/incognito YouTube session, open https://www.youtube.com/robots.txt in the same tab, "
                "export youtube.com cookies, and retry with --cookies-file."
            )
        elif "PO Token" in normalized and "not provided" in normalized:
            normalized = (
                "YouTube requested a PO Token for this client. "
                "Use --po-token-provider for the recommended plugin-based flow, or pass --youtube-client mweb "
                "and --po-token 'mweb.gvs+TOKEN'."
            )
        elif "No title found in player responses" in normalized:
            logger.debug("yt-dlp: %s", normalized)
            return

        if self._remember_issue is not None:
            self._remember_issue(normalized)

        if normalized in self._seen_warnings:
            return
        self._seen_warnings.add(normalized)
        logger.warning("yt-dlp: %s", normalized)

    def error(self, message: str) -> None:
        normalized = self._normalize(message)
        if self._remember_issue is not None:
            self._remember_issue(normalized)
        # DownloadManager converts the final exception into a cleaner user-facing message.
        logger.debug("yt-dlp error: %s", normalized)


@runtime_checkable
class YtDlpRunnerProtocol(Protocol):
    """Protocol for yt-dlp access used by DownloadManager."""

    def extract_info(
        self,
        url: str,
        *,
        download: bool = False,
        extra_opts: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Fetch metadata for a URL."""

    def download(self, request: DownloadRequest) -> Path:
        """Download media and return output directory path."""


class YtDlpRunner:
    """Thin wrapper around yt-dlp's Python API."""

    def __init__(self, base_opts: dict[str, Any] | None = None) -> None:
        self._base_opts: dict[str, Any] = base_opts or {}
        self._recent_issues: list[str] = []
        self._yt_logger = _YtDlpLogger(self._remember_issue)
        self._started_items: set[str] = set()
        self._finished_items: set[str] = set()

    def _common_opts(self) -> dict[str, Any]:
        return {
            **self._base_opts,
            "quiet": True,
            "no_warnings": True,
            "logger": self._yt_logger,
            "progress_hooks": [self._progress_hook],
            "progress_with_newline": True,
        }

    def _remember_issue(self, message: str) -> None:
        normalized = " ".join(message.split())
        if not normalized:
            return
        if self._recent_issues and self._recent_issues[-1] == normalized:
            return
        self._recent_issues.append(normalized)
        if len(self._recent_issues) > 10:
            self._recent_issues = self._recent_issues[-10:]

    def _progress_log_level(self) -> int:
        return logging.INFO if logger.isEnabledFor(logging.INFO) else logging.WARNING

    def _progress_details(self, data: dict[str, Any]) -> tuple[str, str, str] | None:
        info = data.get("info_dict")
        if not isinstance(info, dict):
            return None

        raw_id = str(info.get("id") or "").strip()
        raw_title = str(info.get("title") or "").strip()
        index = info.get("playlist_index")
        total = info.get("n_entries") or info.get("playlist_count")

        if isinstance(index, int) and isinstance(total, int):
            prefix = f"item {index}/{total}"
        elif isinstance(index, int):
            prefix = f"item {index}"
        else:
            prefix = "item"

        title = raw_title or raw_id
        if not title and isinstance(index, int):
            title = f"playlist entry {index}"

        filename = data.get("filename")
        fallback_id = str(filename).strip() if filename else ""
        item_id = raw_id or fallback_id or title

        if not item_id or not title:
            return None

        return item_id, prefix, title

    def _progress_hook(self, data: dict[str, Any]) -> None:
        status = str(data.get("status", ""))
        details = self._progress_details(data)
        if details is None:
            return

        item_id, prefix, title = details

        if status == "downloading" and item_id not in self._started_items:
            self._started_items.add(item_id)
            logger.log(self._progress_log_level(), "Downloading %s: %s", prefix, title)
        elif status == "finished" and item_id not in self._finished_items:
            self._finished_items.add(item_id)
            logger.log(self._progress_log_level(), "Finished %s: %s", prefix, title)
        elif status == "error":
            logger.warning("Failed %s: %s", prefix, title)

    def _snapshot_files(self, output_dir: Path) -> dict[Path, tuple[int, int]]:
        snapshot: dict[Path, tuple[int, int]] = {}
        for path in output_dir.rglob("*"):
            if not path.is_file():
                continue
            resolved = path.resolve()
            stat = path.stat()
            snapshot[resolved] = (stat.st_size, stat.st_mtime_ns)
        return snapshot

    def _is_deliverable_media_file(self, path: Path, *, size: int, request: DownloadRequest) -> bool:
        if size <= 0:
            return False

        suffix = path.suffix.lower()
        requested_suffix = f".{request.audio_format.lower().lstrip('.')}"
        known_media_suffixes = {
            ".mp3",
            ".m4a",
            ".flac",
            ".opus",
            ".ogg",
            ".oga",
            ".wav",
            ".aac",
            ".mp4",
            ".mkv",
            ".webm",
            ".m4v",
            ".mov",
            ".avi",
            ".ts",
            ".m2ts",
        }
        return suffix == requested_suffix or suffix in known_media_suffixes

    @staticmethod
    def _artifact_summary(paths: set[Path]) -> str:
        labels = sorted({path.suffix.lower() or path.name for path in paths})
        preview = ", ".join(labels[:3])
        if len(labels) > 3:
            preview += ", ..."
        return preview or "helper artifacts"

    def _build_opts(self, request: DownloadRequest) -> dict[str, Any]:
        outtmpl = str(request.output_dir / "%(uploader)s/%(title)s.%(ext)s")
        opts: dict[str, Any] = {
            **self._common_opts(),
            "outtmpl": outtmpl,
            "overwrites": request.overwrite,
            **request.extra_yt_dlp_opts,
        }

        if request.cookies_from_browser:
            opts["cookiesfrombrowser"] = (request.cookies_from_browser,)

        if request.cookies_file is not None:
            opts["cookiefile"] = str(request.cookies_file)

        return opts

    def extract_info(
        self,
        url: str,
        *,
        download: bool = False,
        extra_opts: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        opts = {**self._common_opts(), **(extra_opts or {})}
        with yt_dlp.YoutubeDL(opts) as ydl:
            info: dict[str, Any] = ydl.extract_info(url, download=download)
            return info

    def download(self, request: DownloadRequest) -> Path:
        self._recent_issues.clear()
        self._started_items.clear()
        self._finished_items.clear()
        request.output_dir.mkdir(parents=True, exist_ok=True)
        before = self._snapshot_files(request.output_dir)
        opts = self._build_opts(request)
        with yt_dlp.YoutubeDL(opts) as ydl:
            exit_code = ydl.download([request.url])

        after = self._snapshot_files(request.output_dir)
        changed_files = {path for path, state in after.items() if before.get(path) != state}
        saved_media_files = {
            path
            for path in changed_files
            if self._is_deliverable_media_file(path, size=after[path][0], request=request)
        }
        helper_files = changed_files - saved_media_files
        media_files_after = {
            path
            for path, state in after.items()
            if self._is_deliverable_media_file(path, size=state[0], request=request)
        }

        if exit_code not in (0, None):
            if request.extra_yt_dlp_opts.get("ignoreerrors") and saved_media_files:
                queued_items = request.expected_playlist_items
                attempted = len(self._started_items)
                finished = len(self._finished_items)
                failed_after_start = max(attempted - finished, 0)

                summary_parts: list[str] = []
                if queued_items is not None:
                    summary_parts.append(f"saved {len(saved_media_files)} of {queued_items} queued item(s)")
                    never_started = max(queued_items - attempted, 0)
                    if never_started:
                        summary_parts.append(f"{never_started} item(s) never reached the actual download stage")
                else:
                    summary_parts.append(f"saved {len(saved_media_files)} item(s)")

                if attempted:
                    summary_parts.append(f"{finished}/{attempted} item(s) reached and finished the download stage")
                if failed_after_start:
                    summary_parts.append(f"{failed_after_start} item(s) started but failed/interrupted")
                if self._recent_issues and (queued_items is None or queued_items > len(saved_media_files)):
                    summary_parts.append(f"Last reported issue: {self._recent_issues[-1]}")

                logger.warning("yt-dlp continued after playlist errors: %s", "; ".join(summary_parts))
                return request.output_dir

            details: list[str] = []
            if self._started_items:
                details.append(f"{len(self._finished_items)} finished / {len(self._started_items)} attempted item(s)")
            else:
                details.append("no item reached the actual download stage")

            if helper_files and not saved_media_files:
                details.append(f"Only non-media helper files were created ({self._artifact_summary(helper_files)})")

            if self._recent_issues:
                details.append(f"Last reported issue: {self._recent_issues[-1]}")

            raise RuntimeError(f"yt-dlp reported download errors and no files were saved ({'; '.join(details)})")

        if not saved_media_files and not media_files_after:
            details = ["yt-dlp finished without producing a final media file"]
            if helper_files:
                details.append(f"Only non-media helper files were created ({self._artifact_summary(helper_files)})")
            if self._recent_issues:
                details.append(f"Last reported issue: {self._recent_issues[-1]}")
            raise RuntimeError("; ".join(details))

        if request.extra_yt_dlp_opts.get("ignoreerrors") and saved_media_files:
            logger.log(
                self._progress_log_level(),
                "Playlist download saved %d item(s)",
                len(saved_media_files),
            )

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
