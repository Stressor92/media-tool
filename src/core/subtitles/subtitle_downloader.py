"""
src/core/subtitles/subtitle_downloader.py

High-level orchestration for subtitle download workflow.
Coordinates search, download, and embedding operations.
"""

from __future__ import annotations

import logging
import re
import time
from collections.abc import Callable
from pathlib import Path

from core.translation.subtitle_parser import parse_subtitle_file
from core.video.subtitle_processor import SubtitleTimingProcessor
from src.statistics import EventType, get_collector
from utils.ffmpeg_runner import FFmpegMuxer
from utils.ffprobe_runner import probe_file
from utils.video_hasher import VideoHasher

from .subtitle_match_verifier import SubtitleMatchVerifier
from .subtitle_provider import (
    DownloadResult,
    MovieInfo,
    SubtitleMatch,
    SubtitleProvider,
    extract_title_year_from_filename,
)

logger = logging.getLogger(__name__)


class SubtitleDownloadManager:
    MAX_RUNTIME_DRIFT_SECONDS = 2.0

    """
    Orchestrates complete subtitle download workflow.

    Handles:
    - Movie info extraction
    - Subtitle search and selection
    - Download and format conversion
    - MKV embedding
    """

    def __init__(self, provider: SubtitleProvider, ffmpeg_runner: FFmpegMuxer):
        """
        Initialize download manager.

        Args:
            provider: Subtitle provider (OpenSubtitles, etc.)
            ffmpeg_runner: FFmpeg runner for embedding operations
        """
        self.provider = provider
        self.ffmpeg = ffmpeg_runner
        self.hasher = VideoHasher()
        self.timing_processor = SubtitleTimingProcessor()
        self.match_verifier = SubtitleMatchVerifier()

    def process(
        self,
        video_path: Path,
        languages: list[str] | None = None,
        auto_select: bool = True,
        embed: bool = True,
        overwrite: bool = False,
        verify_with_whisper: bool = False,
        verify_model: str = "tiny",
        selection_callback: Callable[[list[SubtitleMatch]], SubtitleMatch | None] | None = None,
    ) -> DownloadResult:
        """
        Complete subtitle download workflow:

        1. Check if subtitles already exist (skip if overwrite=False)
        2. Calculate video hash and extract metadata
        3. Search for subtitles
        4. Select best match (auto or interactive)
        5. Download subtitle file
        6. Convert format if needed (e.g., SUB to SRT)
        7. Embed into MKV (optional)
        8. Return result

        Args:
            video_path: Path to MKV file
            languages: Preferred subtitle languages (priority order)
            auto_select: Auto-select best match or prompt user
            embed: Embed into MKV or save as external file
            overwrite: Overwrite existing subtitles

        Returns:
            DownloadResult with success status and metadata
        """
        if languages is None:
            languages = ["en"]
        start = time.perf_counter()

        # Step 1: Pre-checks
        if not self._should_process_file(video_path, overwrite):
            return DownloadResult(success=False, message="Subtitles already exist (use --overwrite to replace)")

        # Step 2: Extract movie info
        try:
            movie_info = self._extract_movie_info(video_path)
        except Exception as e:
            return DownloadResult(success=False, message=f"Failed to analyze video file: {e}")

        # Step 3: Search for subtitles
        matches = self.provider.search(movie_info, languages)

        if not matches:
            return DownloadResult(success=False, message="No subtitles found", fallback_suggestion="whisper")

        # Step 4: Select best match
        release_hint = self._build_release_hint(video_path)
        if auto_select:
            best_match = self.provider.get_best_match(matches, release_hint=release_hint, movie_info=movie_info)
        else:
            if selection_callback is None:
                return DownloadResult(success=False, message="Interactive selection requires a CLI selection callback")
            best_match = selection_callback(matches)

        if not best_match:
            return DownloadResult(success=False, message="No match selected")

        # Step 5: Download subtitle
        try:
            subtitle_path = self._download_subtitle(best_match, video_path)
        except Exception as e:
            return DownloadResult(success=False, message=f"Download failed: {e}")

        # Step 6: Convert format if needed
        if best_match.format.lower() != "srt":
            try:
                subtitle_path = self._convert_subtitle_format(subtitle_path, best_match.format)
            except Exception as e:
                logger.warning(f"Format conversion failed: {e}, using original")

        timing_result = self._validate_and_sync_subtitle(
            subtitle_path=subtitle_path,
            video_path=video_path,
            video_duration=movie_info.duration,
            language=best_match.language,
            verify_with_whisper=verify_with_whisper,
            verify_model=verify_model,
        )
        if len(timing_result) == 2:
            timing_ok, timing_note = timing_result
            timing_fallback = None
        else:
            timing_ok, timing_note, timing_fallback = timing_result
        if not timing_ok:
            return DownloadResult(
                success=False,
                message=timing_note or "Downloaded subtitle does not fit the video runtime",
                subtitle_path=subtitle_path,
                subtitle_info=best_match,
                fallback_suggestion=timing_fallback or "manual",
            )

        # Step 7: Embed into MKV (optional)
        if embed:
            success = self._embed_subtitle(video_path, subtitle_path, best_match.language)
            if success:
                try:
                    get_collector().record(
                        EventType.SUBTITLE_DOWNLOADED,
                        duration_seconds=time.perf_counter() - start,
                        language=best_match.language,
                        source="opensubtitles",
                    )
                except Exception:
                    logger.debug("Stats recording failed", exc_info=True)
                # Clean up external file after embedding
                subtitle_path.unlink()
                return DownloadResult(
                    success=True,
                    message=f"Embedded {best_match.language} subtitle{timing_note or ''}",
                    subtitle_info=best_match,
                )
            else:
                logger.warning("Embedding failed, keeping external subtitle file")

        try:
            get_collector().record(
                EventType.SUBTITLE_DOWNLOADED,
                duration_seconds=time.perf_counter() - start,
                language=best_match.language,
                source="opensubtitles",
            )
        except Exception:
            logger.debug("Stats recording failed", exc_info=True)

        return DownloadResult(
            success=True,
            message=f"Downloaded to {subtitle_path}{timing_note or ''}",
            subtitle_path=subtitle_path,
            subtitle_info=best_match,
        )

    def _should_process_file(self, video_path: Path, overwrite: bool) -> bool:
        """Check if file should be processed (doesn't already have subtitles)."""

        if not video_path.exists():
            raise FileNotFoundError(f"Video file not found: {video_path}")

        if video_path.suffix.lower() != ".mkv":
            raise ValueError(f"Not an MKV file: {video_path}")

        if overwrite:
            return True

        # Check if subtitle track already exists
        try:
            info = probe_file(video_path)
            subtitle_tracks = [s for s in info.streams if s.get("codec_type") == "subtitle"]
            return len(subtitle_tracks) == 0
        except Exception:
            # If we can't probe, assume we should process
            return True

    def _extract_movie_info(self, video_path: Path) -> MovieInfo:
        """
        Extract all relevant info for matching.

        Uses:
        - OpenSubtitles hash (required)
        - FFprobe for duration and metadata
        - Filename parsing for title/year
        """

        # Calculate hash
        file_hash = self.hasher.calculate_hash(video_path)
        file_size = video_path.stat().st_size

        # Get duration from FFprobe
        try:
            probe_result = probe_file(video_path)
            duration = float(probe_result.format.get("duration", 0))
        except Exception:
            duration = 0.0

        # Parse filename for metadata
        title, year = self._parse_filename(video_path.stem)

        return MovieInfo(
            file_path=video_path, file_hash=file_hash, file_size=file_size, duration=duration, title=title, year=year
        )

    def _parse_filename(self, filename: str) -> tuple[str | None, int | None]:
        """
        Extract a cleaner title and optional year from noisy media filenames.

        Examples:
        - "Movie.Name.2020.1080p.BluRay.mkv" → ("Movie Name", 2020)
        - "Movie Name [Directors Cut] (2020) [DVD]_subtitled.mkv" → ("Movie Name", 2020)
        """

        return extract_title_year_from_filename(filename)

    def _build_release_hint(self, video_path: Path) -> str:
        """Combine file and folder names into a better hint for provider-side release matching."""
        parent_name = video_path.parent.name.strip()
        stem = video_path.stem.strip()
        if parent_name and parent_name.lower() != stem.lower():
            return f"{stem} {parent_name}"
        return stem

    def _download_subtitle(self, match: SubtitleMatch, video_path: Path) -> Path:
        """Download subtitle file to appropriate location."""

        # Create output path next to video file
        subtitle_path = video_path.with_suffix(f".{match.language}.srt")

        return self.provider.download(match, subtitle_path)

    def _convert_subtitle_format(self, subtitle_path: Path, source_format: str) -> Path:
        """
        Convert subtitle format to SRT if needed.

        Currently only handles basic conversions.
        For complex formats, might need external tools.
        """

        normalized_format = source_format.strip().lower()
        if normalized_format in {"", "srt", "unknown"}:
            return subtitle_path

        # For now, just log and return as-is for real non-SRT subtitle formats.
        # TODO: Implement format conversion (SUB, ASS, etc. to SRT)
        logger.warning("Format conversion from %s to SRT not implemented yet", source_format)

        return subtitle_path

    def _validate_and_sync_subtitle(
        self,
        subtitle_path: Path,
        video_path: Path,
        video_duration: float,
        language: str,
        verify_with_whisper: bool,
        verify_model: str,
    ) -> tuple[bool, str | None, str | None]:
        """Validate runtime fit and optionally verify suspicious matches with Whisper."""

        if not subtitle_path.exists():
            return False, "Downloaded subtitle file is missing", "manual"

        if video_duration <= 0:
            return True, " (warning: video duration unavailable for runtime checks)", None

        subtitle_duration = self._estimate_subtitle_duration(subtitle_path)
        if subtitle_duration is None or subtitle_duration <= 0:
            return False, "Could not determine subtitle runtime", "manual"

        drift_seconds = abs(video_duration - subtitle_duration)
        if drift_seconds <= self.MAX_RUNTIME_DRIFT_SECONDS:
            return True, None, None

        if not verify_with_whisper:
            # Legacy fallback mode: try to sync moderate runtime drift and keep throughput high.
            drift_ratio = drift_seconds / max(video_duration, 1.0)
            if subtitle_path.suffix.lower() == ".srt" and drift_ratio <= 0.08:
                sync_result = self.timing_processor.sync_to_video(
                    subtitle_path,
                    video_duration=video_duration,
                    wav_duration=subtitle_duration,
                )
                if sync_result.success:
                    return True, f" (timing adjusted {sync_result.scale_factor:.4f}x to fit runtime)", None
            return True, f" (warning: runtime differs by {drift_seconds:.0f}s)", None

        try:
            verification = self.match_verifier.verify(
                video_path,
                subtitle_path,
                video_duration=video_duration,
                language=language,
                model=verify_model.lower(),
            )
        except Exception as exc:
            logger.warning("Whisper subtitle verification failed unexpectedly: %s", exc)
            verification = None

        if verification is None or verification.status == "skipped":
            return (
                True,
                " (warning: Whisper verification unavailable; accepted without advanced validation)",
                None,
            )

        if verification.status == "reject":
            return (
                False,
                f"{verification.message} [confidence={verification.confidence_score:.2f}]",
                "manual",
            )

        if verification.status == "uncertain":
            return (
                False,
                f"{verification.message} [confidence={verification.confidence_score:.2f}]",
                "interactive",
            )

        # Passed Whisper verification: scale only if text is strong and drift appears linear.
        if (
            subtitle_path.suffix.lower() == ".srt"
            and verification.average_text_similarity >= 0.60
            and (verification.drift_trend_seconds is not None and verification.drift_trend_seconds <= 2.5)
        ):
            sync_result = self.timing_processor.sync_to_video(
                subtitle_path,
                video_duration=video_duration,
                wav_duration=subtitle_duration,
            )
            if sync_result.success:
                return (
                    True,
                    " (Whisper verified; timing adjusted "
                    f"{sync_result.scale_factor:.4f}x, confidence={verification.confidence_score:.2f})",
                    None,
                )
            logger.warning("Subtitle timing sync failed for %s: %s", subtitle_path, sync_result.error_message)
            return False, "Failed to adjust subtitle timing after Whisper verification", "manual"

        return (
            True,
            f" (Whisper verified; confidence={verification.confidence_score:.2f})",
            None,
        )

    def _estimate_subtitle_duration(self, subtitle_path: Path) -> float | None:
        """Estimate the subtitle runtime from the last cue end timestamp."""
        try:
            text = subtitle_path.read_text(encoding="utf-8-sig", errors="replace")
        except Exception as exc:
            logger.debug("Failed to read subtitle timing for %s: %s", subtitle_path, exc)
            return None

        # Be permissive: downloaded SRTs sometimes contain leading whitespace.
        timestamp_matches = re.findall(
            r"(?m)^\s*(\d{1,2}:\d{2}:\d{2}[,.]\d{2,3})\s*-->\s*(\d{1,2}:\d{2}:\d{2}[,.]\d{2,3})",
            text,
        )
        if timestamp_matches:
            try:
                return max(self._timestamp_to_seconds(end) for _start, end in timestamp_matches)
            except Exception as exc:
                logger.debug("Failed to inspect raw subtitle timestamps for %s: %s", subtitle_path, exc)

        try:
            document = parse_subtitle_file(subtitle_path)
        except Exception as exc:
            logger.debug("Failed to parse subtitle timing for %s: %s", subtitle_path, exc)
            return None

        if not document.segments:
            return None

        try:
            return max(self._timestamp_to_seconds(segment.end) for segment in document.segments)
        except Exception as exc:
            logger.debug("Failed to inspect subtitle timestamps for %s: %s", subtitle_path, exc)
            return None

    @staticmethod
    def _timestamp_to_seconds(value: str) -> float:
        """Convert normalized SRT/VTT-style timestamps to seconds."""
        normalized = value.strip().replace(".", ",")
        hours, minutes, rest = normalized.split(":")
        seconds, millis = rest.split(",")
        return int(hours) * 3600.0 + int(minutes) * 60.0 + int(seconds) + (int(millis[:3].ljust(3, "0")) / 1000.0)

    def _embed_subtitle(self, video_path: Path, subtitle_path: Path, language: str) -> bool:
        """
        Embed subtitle into MKV file.

        Uses existing FFmpegMuxer.add_subtitle_to_mkv method.
        """

        try:
            # Use existing MKV muxing functionality
            # This assumes FFmpegMuxer has a method for this
            result = self.ffmpeg.add_subtitle_to_mkv(
                video_path, subtitle_path, language=language, title=f"{language.upper()} (OpenSubtitles)"
            )

            return result.success

        except Exception as e:
            logger.error(f"Failed to embed subtitle: {e}")
            return False
