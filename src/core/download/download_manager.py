from __future__ import annotations

import logging
import re
import shutil
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
            info = self._extract_info(request)
            track_info = parse_track_info(info)
            enriched_request = self._enrich_request(request, info)
            effective_request = self._download_with_cookie_fallback(enriched_request)
            output_path = (
                effective_request.output_dir
                if self._uses_playlist_tolerant_mode(request)
                else self._resolve_output_path(effective_request, track_info)
            )
            return DownloadResult(
                status=DownloadStatus.SUCCESS,
                request=request,
                output_path=output_path,
                track_info=track_info,
            )
        except Exception as exc:  # noqa: BLE001
            error_message = self._format_error_message(exc, request)
            if self._is_expected_download_error(exc):
                logger.warning("Download failed for %s: %s", request.url, error_message)
            else:
                logger.exception("Unexpected download failure for %s", request.url)
            return DownloadResult(
                status=DownloadStatus.FAILED,
                request=request,
                error_message=error_message,
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
                    if self._is_stale_youtube_cookie_error(retry_exc):
                        logger.warning(
                            "Browser cookies from %s look stale/rotated for YouTube; a fresh private-session export is needed",
                            browser,
                        )
                    if self._is_rate_limit_error(retry_exc):
                        logger.warning(
                            "YouTube rate-limited the current session during cookie retry; stopping automatic browser retries"
                        )
                        raise
                    if not self._is_auth_error(retry_exc):
                        raise

            raise last_error from exc

    def _extract_info(self, request: DownloadRequest) -> dict[str, Any]:
        youtube_extract_opts: dict[str, Any] = {}
        if self._looks_like_youtube_url(request.url):
            js_runtimes = self._default_js_runtimes()
            if js_runtimes is not None:
                youtube_extract_opts["js_runtimes"] = js_runtimes

        if self._uses_playlist_tolerant_mode(request):
            extra_opts = {"extract_flat": "in_playlist", "ignoreerrors": True, **youtube_extract_opts}
            info = self._runner.extract_info(
                request.url,
                download=False,
                extra_opts=extra_opts,
            )
            if not isinstance(info, dict) or not info:
                raise RuntimeError(self._nothing_to_download_message(request))

            self._log_playlist_summary(info)

            if self._looks_like_collection_url(request.url) and self._available_playlist_items(info) == 0:
                raise RuntimeError(self._nothing_to_download_message(request))

            return info

        if youtube_extract_opts:
            return self._runner.extract_info(request.url, download=False, extra_opts=youtube_extract_opts)
        return self._runner.extract_info(request.url, download=False)

    @staticmethod
    def _looks_like_collection_url(url: str) -> bool:
        lowered = url.lower()
        return any(token in lowered for token in ("list=", "/sets/", "/playlist", "/album/"))

    def _uses_playlist_tolerant_mode(self, request: DownloadRequest) -> bool:
        return request.media_type == MediaType.SERIES or self._looks_like_collection_url(request.url)

    @staticmethod
    def _looks_like_youtube_url(url: str) -> bool:
        lowered = url.lower()
        return "youtube.com" in lowered or "youtu.be" in lowered

    @staticmethod
    def _looks_like_soundcloud_url(url: str) -> bool:
        return "soundcloud.com" in url.lower()

    def _playlist_entries(self, info: dict[str, Any] | None) -> list[Any]:
        if not isinstance(info, dict):
            return []
        entries = info.get("entries")
        return entries if isinstance(entries, list) else []

    def _available_playlist_items(self, info: dict[str, Any] | None) -> int | None:
        entries = self._playlist_entries(info)
        if not entries:
            return None
        return sum(1 for entry in entries if entry)

    def _nothing_to_download_message(self, request: DownloadRequest) -> str:
        target = "playlist/album" if self._looks_like_collection_url(request.url) else "media URL"
        return (
            f"Nothing to download: the {target} returned no downloadable items or no usable metadata. "
            "This usually means the link is empty, private, removed, geo-blocked, or the network/provider is currently unreachable. "
            "Check your internet connection and verify the URL, then retry."
        )

    def _log_playlist_summary(self, info: dict[str, Any] | None) -> None:
        entries = self._playlist_entries(info)
        if not entries:
            return

        total = len(entries)
        available = sum(1 for entry in entries if entry)
        title = str(info.get("playlist_title") or info.get("title") or "Playlist")
        self._log_user_progress(f"Playlist detected: {title} ({available} available / {total} total entries)")

        for index, entry in enumerate(entries, start=1):
            if not isinstance(entry, dict):
                self._log_user_progress(f"Playlist item {index}/{total}: unavailable or hidden entry")
                continue

            item_title = str(entry.get("title") or entry.get("id") or "unknown title")
            uploader = str(entry.get("channel") or entry.get("uploader") or "").strip()
            suffix = f" — {uploader}" if uploader else ""
            self._log_user_progress(f"Playlist item {index}/{total}: {item_title}{suffix}")

    def _log_user_progress(self, message: str) -> None:
        level = logging.INFO if logger.isEnabledFor(logging.INFO) else logging.WARNING
        logger.log(level, message)

    def _should_retry_with_browser_cookies(self, request: DownloadRequest, exc: Exception) -> bool:
        if request.cookies_from_browser or request.cookies_file is not None:
            return False
        if self._looks_like_soundcloud_url(request.url):
            return True
        return self._is_auth_error(exc)

    def _youtube_cookie_refresh_help(self, *, from_browser_retry: bool) -> str:
        intro = (
            "Automatic browser-cookie retry found stale or rotated YouTube cookies. "
            if from_browser_retry
            else "YouTube rejected the supplied cookies because they appear stale or rotated. "
        )
        return (
            intro
            + "Create a fresh cookie export like this: "
            + "1) open a new private/incognito window and sign in to YouTube; "
            + "2) in the same tab open https://www.youtube.com/robots.txt; "
            + "3) export only the youtube.com cookies with a browser extension into a Netscape-style .txt file; "
            + "4) close the private window and rerun with --cookies-file <path>. "
            + "Avoid reusing normal-session browser cookies after they have been rotated."
        )

    @staticmethod
    def _youtube_po_token_help() -> str:
        return (
            "For harder YouTube cases, enable PO Token support with the recommended mweb client. "
            "Preferred setup: install a yt-dlp PO Token Provider plugin and rerun with "
            "--po-token-provider (alias: --youtube-use-po-token-provider). Advanced manual mode: pass "
            "--youtube-client mweb and --po-token / --youtube-po-token 'mweb.gvs+TOKEN'."
        )

    def _youtube_recovery_order(self) -> str:
        return (
            "Recommended order: first use a fresh --cookies-file export; then, if YouTube says the session is "
            "rate-limited, wait up to an hour before retrying; finally, optionally enable PO Token provider support "
            "for harder YouTube cases with --youtube-use-po-token-provider."
        )

    def _format_error_message(self, exc: Exception, request: DownloadRequest) -> str:
        cleaned = self._clean_error_text(str(exc))

        if self._is_network_error(exc):
            return (
                "Network connection problem: media-tool could not reach the provider or retrieve metadata/files. "
                "Check your internet connection, DNS/VPN/firewall settings, and verify the URL before retrying."
            )

        if self._is_geo_error(exc):
            return (
                "Geo-restricted content: this media is not available from your location. "
                "Try a VPN/proxy or another source and retry."
            )

        if self._is_stale_youtube_cookie_error(exc):
            return (
                self._youtube_cookie_refresh_help(
                    from_browser_retry=not (request.cookies_from_browser or request.cookies_file is not None)
                )
                + " "
                + self._youtube_recovery_order()
            )

        if self._is_missing_po_token_error(exc):
            return self._youtube_po_token_help() + " " + self._youtube_recovery_order()

        if self._is_youtube_signature_challenge_error(exc):
            return (
                "YouTube signature/challenge verification failed before media download started. "
                "Install a supported JavaScript runtime (Node.js or Deno) and update yt-dlp, then retry. "
                "Use a fresh private/incognito cookie export with --cookies-file <path>. "
                "If needed, enable --youtube-use-po-token-provider for harder YouTube cases. "
                + self._youtube_recovery_order()
            )

        if self._is_rate_limit_error(exc):
            return (
                "YouTube temporarily rate-limited this session. Wait up to an hour before retrying. "
                "Then use a fresh private/incognito cookie export with --cookies-file <path>. "
                "To reduce repeat throttling, the downloader now spaces out YouTube playlist requests automatically. "
                + self._youtube_recovery_order()
            )

        if self._is_auth_error(exc):
            if request.cookies_from_browser or request.cookies_file is not None:
                return (
                    "Authentication required: the provider still refused access with the supplied cookies. "
                    "Refresh the browser session and retry with --cookies-from-browser or --cookies-file. "
                    + self._youtube_recovery_order()
                )
            return (
                "Authentication required: this media needs a signed-in browser session or valid cookies. "
                "Retry with --cookies-from-browser chrome|firefox or --cookies-file <path>. "
                + self._youtube_recovery_order()
            )

        if self._is_availability_error(exc):
            return f"Provider reported this media as unavailable: {cleaned}"

        return cleaned or exc.__class__.__name__

    @staticmethod
    def _clean_error_text(message: str) -> str:
        cleaned = re.sub(r"\x1b\[[0-9;]*m", "", message)
        cleaned = re.sub(r"\[[0-9;]+m", "", cleaned)
        cleaned = cleaned.replace("\r", "\n")
        cleaned = re.sub(r"(?im)^error:\s*", "", cleaned)
        cleaned = re.sub(r"\n{2,}", "\n", cleaned)
        return " ".join(part.strip() for part in cleaned.splitlines() if part.strip())

    def _is_expected_download_error(self, exc: Exception) -> bool:
        return (
            self._is_auth_error(exc)
            or self._is_geo_error(exc)
            or self._is_network_error(exc)
            or self._is_missing_po_token_error(exc)
            or self._is_youtube_signature_challenge_error(exc)
            or self._is_rate_limit_error(exc)
            or self._is_availability_error(exc)
            or self._is_no_downloadable_items_error(exc)
        )

    def _is_youtube_signature_challenge_error(self, exc: Exception) -> bool:
        message = self._clean_error_text(str(exc)).lower()
        signature_fragments = (
            "signature solving failed",
            "n challenge solving failed",
            "the page needs to be reloaded",
            "unable to download video data: http error 403: forbidden",
            "yt-dlp/wiki/ejs",
        )
        return any(fragment in message for fragment in signature_fragments)

    def _is_auth_error(self, exc: Exception) -> bool:
        message = self._clean_error_text(str(exc)).lower()
        auth_fragments = (
            "login required",
            "sign in",
            "authentication",
            "age-restricted",
            "cookies",
            "403",
        )
        return any(fragment in message for fragment in auth_fragments)

    def _is_stale_youtube_cookie_error(self, exc: Exception) -> bool:
        message = self._clean_error_text(str(exc)).lower()
        stale_fragments = (
            "youtube account cookies are no longer valid",
            "rotated in the browser as a security measure",
            "exporting-youtube-cookies",
            "supplied cookies are no longer valid",
        )
        return any(fragment in message for fragment in stale_fragments)

    def _is_missing_po_token_error(self, exc: Exception) -> bool:
        message = self._clean_error_text(str(exc)).lower()
        pot_fragments = (
            "po token which was not provided",
            "po token required",
            "gvs po token",
            "missing_pot",
        )
        return any(fragment in message for fragment in pot_fragments)

    def _is_rate_limit_error(self, exc: Exception) -> bool:
        message = self._clean_error_text(str(exc)).lower()
        rate_limit_fragments = (
            "rate-limited by youtube",
            "current session has been rate-limited",
            "try again later",
            "too many requests",
        )
        return any(fragment in message for fragment in rate_limit_fragments)

    def _is_geo_error(self, exc: Exception) -> bool:
        message = self._clean_error_text(str(exc)).lower()
        geo_fragments = (
            "geo restriction",
            "geo-restricted",
            "not available from your location",
            "not available in your country",
            "has not made this video available in your country",
            "not made this video available in your country",
            "geoblock",
        )
        return any(fragment in message for fragment in geo_fragments)

    def _is_network_error(self, exc: Exception) -> bool:
        message = self._clean_error_text(str(exc)).lower()
        network_fragments = (
            "temporary failure in name resolution",
            "getaddrinfo failed",
            "name or service not known",
            "failed to establish a new connection",
            "max retries exceeded",
            "connection refused",
            "connection reset",
            "network is unreachable",
            "unable to download webpage",
            "unable to download api page",
            "remote end closed connection",
            "timed out",
            "read timed out",
        )
        return any(fragment in message for fragment in network_fragments)

    def _is_no_downloadable_items_error(self, exc: Exception) -> bool:
        message = self._clean_error_text(str(exc)).lower()
        no_items_fragments = (
            "nothing to download",
            "no downloadable items",
            "no usable metadata",
        )
        return any(fragment in message for fragment in no_items_fragments)

    def _is_availability_error(self, exc: Exception) -> bool:
        message = self._clean_error_text(str(exc)).lower()
        availability_fragments = (
            "video unavailable",
            "media unavailable",
            "private video",
            "unsupported url",
            "unsupported site",
            "unable to extract",
            "not available",
        )
        return any(fragment in message for fragment in availability_fragments)

    @staticmethod
    def _ensure_extractor_args(extra: dict[str, Any], ie_key: str) -> dict[str, list[str]]:
        extractor_args = extra.get("extractor_args")
        if not isinstance(extractor_args, dict):
            extractor_args = {}
            extra["extractor_args"] = extractor_args

        ie_args = extractor_args.get(ie_key)
        if not isinstance(ie_args, dict):
            ie_args = {}
            extractor_args[ie_key] = ie_args

        normalized: dict[str, list[str]] = {}
        for key, value in ie_args.items():
            if isinstance(value, list):
                normalized[str(key)] = [str(item) for item in value]
            else:
                normalized[str(key)] = [str(value)]
        extractor_args[ie_key] = normalized
        return normalized

    def _apply_youtube_extractor_args(self, request: DownloadRequest, extra: dict[str, Any]) -> None:
        if not self._looks_like_youtube_url(request.url):
            return

        youtube_args = self._ensure_extractor_args(extra, "youtube")

        player_client = request.youtube_player_client
        if request.youtube_use_po_token_provider and not player_client:
            player_client = "mweb"
        if player_client:
            youtube_args["player_client"] = [player_client]

        fetch_pot = request.youtube_fetch_pot
        if request.youtube_use_po_token_provider and not fetch_pot:
            fetch_pot = "always"
        if fetch_pot:
            youtube_args["fetch_pot"] = [fetch_pot]

        if request.youtube_visitor_data:
            youtube_args["visitor_data"] = [request.youtube_visitor_data]

        if request.youtube_po_token:
            token = request.youtube_po_token.strip()
            if token and "+" not in token:
                token_client = player_client or "mweb"
                token = f"{token_client}.gvs+{token}"
            if token:
                youtube_args["po_token"] = [token]

    @staticmethod
    def _default_js_runtimes() -> dict[str, dict[str, Any]] | None:
        if shutil.which("node"):
            return {"node": {}}
        return None

    def _enrich_request(self, request: DownloadRequest, info: dict[str, Any]) -> DownloadRequest:
        extra: dict[str, Any] = {
            **request.extra_yt_dlp_opts,
            "format": build_format_string(request),
            "postprocessors": build_postprocessors(request),
            "writesubtitles": request.embed_subtitles,
            "subtitleslangs": list(request.subtitle_languages),
            "writethumbnail": request.embed_thumbnail,
        }

        if self._uses_playlist_tolerant_mode(request):
            extra["ignoreerrors"] = True

        if self._looks_like_youtube_url(request.url):
            extra.setdefault("sleep_interval", 5)
            extra.setdefault("max_sleep_interval", 10)
            extra.setdefault("sleep_interval_requests", 1)
            if "js_runtimes" not in extra:
                js_runtimes = self._default_js_runtimes()
                if js_runtimes is not None:
                    extra["js_runtimes"] = js_runtimes
            self._apply_youtube_extractor_args(request, extra)

        if self._looks_like_soundcloud_url(request.url):
            extra.setdefault("format", "bestaudio/best")

        expected_items = self._available_playlist_items(info)

        if request.media_type == MediaType.SERIES:
            if request.extract_audio:
                # Audio-first series downloads should land in a music-like structure.
                extra["outtmpl"] = str(
                    request.output_dir
                    / "%(uploader|Unknown Author)s"
                    / "%(album|Unknown Album)s"
                    / "%(title|Unknown Track)s.%(ext)s"
                )
                return replace(request, extra_yt_dlp_opts=extra, expected_playlist_items=expected_items)

            series = info.get("series") or info.get("playlist_title") or info.get("title") or "Unknown Series"
            season = info.get("season_number", 1)
            safe_series = str(series).strip() or "Unknown Series"
            safe_season = int(season) if isinstance(season, int) else 1
            extra["outtmpl"] = str(
                request.output_dir
                / safe_series
                / f"Season {safe_season:02d}"
                / "%(playlist_index)s - %(title)s.%(ext)s"
            )

        return replace(request, extra_yt_dlp_opts=extra, expected_playlist_items=expected_items)

    def _dry_run(self, request: DownloadRequest) -> DownloadResult:
        info = self._extract_info(request)
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
