from __future__ import annotations

import logging
from dataclasses import replace
from pathlib import Path
from typing import Any

from core.download.format_selector import build_format_string, build_postprocessors
from core.download.models import DownloadRequest, DownloadResult, DownloadStatus, MediaType, TrackInfo
from core.download.yt_dlp_runner import YtDlpRunner, YtDlpRunnerProtocol, parse_track_info

logger = logging.getLogger(__name__)


class DownloadManager:
    """Orchestrates yt-dlp extraction, option enrichment, and download flow."""

    def __init__(self, runner: YtDlpRunnerProtocol | None = None) -> None:
        self._runner: YtDlpRunnerProtocol = runner or YtDlpRunner()

    def download(self, request: DownloadRequest) -> DownloadResult:
        """Execute one complete download cycle."""
        logger.info("Starting download: %s [%s]", request.url, request.media_type.value)

        if request.dry_run:
            return self._dry_run(request)

        try:
            info = self._runner.extract_info(request.url, download=False)
            track_info = parse_track_info(info)
            enriched_request = self._enrich_request(request, info)
            effective_request = self._download_with_cookie_fallback(enriched_request)
            output_path = self._resolve_output_path(effective_request, track_info)
            return DownloadResult(
                status=DownloadStatus.SUCCESS,
                request=request,
                output_path=output_path,
                track_info=track_info,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Download failed: %s", exc)
            return DownloadResult(
                status=DownloadStatus.FAILED,
                request=request,
                error_message=str(exc),
            )

    def download_batch(self, requests: list[DownloadRequest]) -> list[DownloadResult]:
        """Process multiple requests sequentially."""
        return [self.download(item) for item in requests]

    def _download_with_cookie_fallback(self, request: DownloadRequest) -> DownloadRequest:
        try:
            self._runner.download(request)
            return request
        except Exception as exc:  # noqa: BLE001
            if not self._should_retry_with_browser_cookies(request, exc):
                raise

            logger.warning("Login required - retrying with browser cookies")
            last_error: Exception = exc
            for browser in ("chrome", "firefox"):
                retry_request = replace(request, cookies_from_browser=browser)
                try:
                    self._runner.download(retry_request)
                    return retry_request
                except Exception as retry_exc:  # noqa: BLE001
                    last_error = retry_exc
                    if not self._is_auth_error(retry_exc):
                        raise

            raise last_error

    def _should_retry_with_browser_cookies(self, request: DownloadRequest, exc: Exception) -> bool:
        if request.cookies_from_browser or request.cookies_file is not None:
            return False
        return self._is_auth_error(exc)

    def _is_auth_error(self, exc: Exception) -> bool:
        message = str(exc).lower()
        auth_fragments = (
            "login required",
            "sign in",
            "authentication",
            "age-restricted",
            "cookies",
            "403",
        )
        return any(fragment in message for fragment in auth_fragments)

    def _enrich_request(self, request: DownloadRequest, info: dict[str, Any]) -> DownloadRequest:
        extra: dict[str, Any] = {
            **request.extra_yt_dlp_opts,
            "format": build_format_string(request),
            "postprocessors": build_postprocessors(request),
            "writesubtitles": request.embed_subtitles,
            "subtitleslangs": list(request.subtitle_languages),
            "writethumbnail": request.embed_thumbnail,
        }

        if request.media_type == MediaType.SERIES:
            series = info.get("series", "Unknown Series")
            season = info.get("season_number", 1)
            safe_series = str(series).strip() or "Unknown Series"
            safe_season = int(season) if isinstance(season, int) else 1
            extra["outtmpl"] = str(
                request.output_dir
                / safe_series
                / f"Season {safe_season:02d}"
                / "%(series)s - S%(season_number)02dE%(episode_number)02d - %(title)s.%(ext)s"
            )

        return replace(request, extra_yt_dlp_opts=extra)

    def _dry_run(self, request: DownloadRequest) -> DownloadResult:
        info = self._runner.extract_info(request.url, download=False)
        track_info = parse_track_info(info)
        logger.info("[DRY-RUN] Would download: %s -> %s", track_info.title, request.output_dir)
        return DownloadResult(
            status=DownloadStatus.SKIPPED,
            request=request,
            track_info=track_info,
            skipped_reason="dry_run",
        )

    def _resolve_output_path(self, request: DownloadRequest, track_info: TrackInfo) -> Path:
        ext = "mkv" if request.media_type != MediaType.MUSIC else request.audio_format
        safe_title = "".join(c if c.isalnum() or c in " .-_()" else "_" for c in track_info.title)
        safe_uploader = "".join(c if c.isalnum() or c in " .-_()" else "_" for c in track_info.uploader)
        return request.output_dir / safe_uploader / f"{safe_title}.{ext}"
