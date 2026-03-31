"""
src/core/subtitles/subtitle_downloader.py

High-level orchestration for subtitle download workflow.
Coordinates search, download, and embedding operations.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Callable, List, Optional

from .subtitle_provider import SubtitleProvider, SubtitleMatch, MovieInfo, DownloadResult
from utils.video_hasher import VideoHasher
from utils.ffmpeg_runner import FFmpegMuxer
from utils.ffprobe_runner import probe_file

logger = logging.getLogger(__name__)


class SubtitleDownloadManager:
    """
    Orchestrates complete subtitle download workflow.

    Handles:
    - Movie info extraction
    - Subtitle search and selection
    - Download and format conversion
    - MKV embedding
    """

    def __init__(
        self,
        provider: SubtitleProvider,
        ffmpeg_runner: FFmpegMuxer
    ):
        """
        Initialize download manager.

        Args:
            provider: Subtitle provider (OpenSubtitles, etc.)
            ffmpeg_runner: FFmpeg runner for embedding operations
        """
        self.provider = provider
        self.ffmpeg = ffmpeg_runner
        self.hasher = VideoHasher()

    def process(
        self,
        video_path: Path,
        languages: Optional[List[str]] = None,
        auto_select: bool = True,
        embed: bool = True,
        overwrite: bool = False,
        selection_callback: Optional[Callable[[List[SubtitleMatch]], Optional[SubtitleMatch]]] = None,
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

        # Step 1: Pre-checks
        if not self._should_process_file(video_path, overwrite):
            return DownloadResult(
                success=False,
                message="Subtitles already exist (use --overwrite to replace)"
            )

        # Step 2: Extract movie info
        try:
            movie_info = self._extract_movie_info(video_path)
        except Exception as e:
            return DownloadResult(
                success=False,
                message=f"Failed to analyze video file: {e}"
            )

        # Step 3: Search for subtitles
        matches = self.provider.search(movie_info, languages)

        if not matches:
            return DownloadResult(
                success=False,
                message="No subtitles found",
                fallback_suggestion="whisper"
            )

        # Step 4: Select best match
        if auto_select:
            best_match = self.provider.get_best_match(matches)
        else:
            if selection_callback is None:
                return DownloadResult(
                    success=False,
                    message="Interactive selection requires a CLI selection callback"
                )
            best_match = selection_callback(matches)

        if not best_match:
            return DownloadResult(
                success=False,
                message="No match selected"
            )

        # Step 5: Download subtitle
        try:
            subtitle_path = self._download_subtitle(best_match, video_path)
        except Exception as e:
            return DownloadResult(
                success=False,
                message=f"Download failed: {e}"
            )

        # Step 6: Convert format if needed
        if best_match.format.lower() != "srt":
            try:
                subtitle_path = self._convert_subtitle_format(subtitle_path, best_match.format)
            except Exception as e:
                logger.warning(f"Format conversion failed: {e}, using original")

        # Step 7: Embed into MKV (optional)
        if embed:
            success = self._embed_subtitle(video_path, subtitle_path, best_match.language)
            if success:
                # Clean up external file after embedding
                subtitle_path.unlink()
                return DownloadResult(
                    success=True,
                    message=f"Embedded {best_match.language} subtitle",
                    subtitle_info=best_match
                )
            else:
                logger.warning("Embedding failed, keeping external subtitle file")

        return DownloadResult(
            success=True,
            message=f"Downloaded to {subtitle_path}",
            subtitle_path=subtitle_path,
            subtitle_info=best_match
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
            file_path=video_path,
            file_hash=file_hash,
            file_size=file_size,
            duration=duration,
            title=title,
            year=year
        )

    def _parse_filename(self, filename: str) -> tuple[Optional[str], Optional[int]]:
        """
        Extract title and year from filename.

        Examples:
        - "Movie.Name.2020.1080p.BluRay.mkv" → ("Movie Name", 2020)
        - "Movie Name (2020) [DVD].mkv" → ("Movie Name", 2020)
        """
        import re

        # Pattern: (title) (year) [release info]
        pattern = r'^(.+?)[\.\s]+\(?(\d{4})\)?'
        match = re.search(pattern, filename)

        if match:
            title = match.group(1).replace(".", " ").strip()
            year = int(match.group(2))
            return title, year

        return None, None

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

        if source_format.lower() == "srt":
            return subtitle_path

        # For now, just log and return as-is
        # TODO: Implement format conversion (SUB, ASS, etc. to SRT)
        logger.warning(f"Format conversion from {source_format} to SRT not implemented yet")

        return subtitle_path

    def _embed_subtitle(self, video_path: Path, subtitle_path: Path, language: str) -> bool:
        """
        Embed subtitle into MKV file.

        Uses existing FFmpegMuxer.add_subtitle_to_mkv method.
        """

        try:
            # Use existing MKV muxing functionality
            # This assumes FFmpegMuxer has a method for this
            result = self.ffmpeg.add_subtitle_to_mkv(
                video_path,
                subtitle_path,
                language=language,
                title=f"{language.upper()} (OpenSubtitles)"
            )

            return result.success

        except Exception as e:
            logger.error(f"Failed to embed subtitle: {e}")
            return False