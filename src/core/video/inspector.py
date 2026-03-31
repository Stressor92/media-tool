"""
src/core/inspector.py

Core business logic for scanning a media library and extracting
per-file metadata via ffprobe.

Mirrors: video_list.ps1

Output: list of VideoInfo dataclasses, exportable to CSV.

Rules:
- No print() / no CLI imports
- Returns structured data — caller decides how to render/export
"""

from __future__ import annotations

import csv
import logging
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path

from utils.ffprobe_runner import probe_file

logger = logging.getLogger(__name__)

# Supported video extensions (lowercase)
VIDEO_EXTENSIONS: frozenset[str] = frozenset({".mp4", ".mkv", ".avi"})


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class VideoInfo:
    """
    Metadata for a single video file, extracted via ffprobe.

    Mirrors the PS script's PSCustomObject columns, with Pythonic names.
    """

    file_name: str
    file_path: str
    extension: str
    size_gb: float
    duration: str               # HH:MM:SS
    video_codec: str
    resolution: str             # "1920 x 1080" or "Unknown"
    fps: str                    # "23.98" or "?"
    audio_track_count: int
    audio_languages: str        # comma-separated, e.g. "deu, eng"
    subtitle_track_count: int
    subtitle_languages: str     # comma-separated

    # Internal flag — not exported to CSV
    probe_error: bool = field(default=False, repr=False)
    probe_error_message: str = field(default="", repr=False)

    @property
    def ok(self) -> bool:
        return not self.probe_error


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _format_duration(seconds_str: str) -> str:
    """Convert a decimal seconds string to HH:MM:SS format."""
    try:
        total = int(float(seconds_str))
        h = total // 3600
        m = (total % 3600) // 60
        s = total % 60
        return f"{h:02d}:{m:02d}:{s:02d}"
    except (ValueError, TypeError):
        return "?"


def _parse_fps(r_frame_rate: str) -> str:
    """
    Parse a fractional frame-rate string (e.g. "24000/1001") to a
    human-readable decimal (e.g. "23.98").
    """
    if not r_frame_rate or "/" not in r_frame_rate:
        return r_frame_rate or "?"
    try:
        num_str, den_str = r_frame_rate.split("/")
        num, den = float(num_str), float(den_str)
        if den == 0:
            return r_frame_rate
        return str(round(num / den, 2))
    except (ValueError, ZeroDivisionError):
        return r_frame_rate


def _stream_languages(streams: list[dict]) -> str:
    """Extract language tags from a list of streams, comma-joined."""
    langs = [s.get("tags", {}).get("language", "") for s in streams]
    result = ", ".join(l for l in langs if l)
    return result or "-"


# ---------------------------------------------------------------------------
# Single-file inspection
# ---------------------------------------------------------------------------


def inspect_file(path: Path) -> VideoInfo:
    """
    Extract metadata from a single video file via ffprobe.

    Args:
        path: Path to the video file.

    Returns:
        VideoInfo with all available metadata fields populated.
        On ffprobe failure, returns a VideoInfo with probe_error=True.
    """
    size_gb = round(path.stat().st_size / 1_073_741_824, 2)

    probe = probe_file(path)

    if probe.failed:
        logger.warning("ffprobe failed for: %s", path)
        return VideoInfo(
            file_name=path.name,
            file_path=str(path),
            extension=path.suffix,
            size_gb=size_gb,
            duration="?",
            video_codec="?",
            resolution="?",
            fps="?",
            audio_track_count=0,
            audio_languages="-",
            subtitle_track_count=0,
            subtitle_languages="-",
            probe_error=True,
            probe_error_message=probe.stderr[:300],
        )

    video = probe.first_video()
    audio_streams = probe.audio_streams()
    subtitle_streams = probe.subtitle_streams()
    fmt = probe.format

    # Video metadata
    if video:
        codec = video.get("codec_name", "?")
        w = video.get("width")
        h = video.get("height")
        resolution = f"{w} x {h}" if w and h else "Unknown"
        fps = _parse_fps(video.get("r_frame_rate", ""))
    else:
        codec = "?"
        resolution = "Unknown"
        fps = "?"

    duration = _format_duration(fmt.get("duration", ""))
    audio_langs = _stream_languages(audio_streams)
    sub_langs = _stream_languages(subtitle_streams)

    return VideoInfo(
        file_name=path.name,
        file_path=str(path),
        extension=path.suffix,
        size_gb=size_gb,
        duration=duration,
        video_codec=codec,
        resolution=resolution,
        fps=fps,
        audio_track_count=len(audio_streams),
        audio_languages=audio_langs,
        subtitle_track_count=len(subtitle_streams),
        subtitle_languages=sub_langs,
    )


# ---------------------------------------------------------------------------
# Directory scan
# ---------------------------------------------------------------------------


def scan_directory(
    directory: Path,
    extensions: frozenset[str] = VIDEO_EXTENSIONS,
    recursive: bool = True,
    progress_callback: Callable[[int, int, Path], None] | None = None,
) -> list[VideoInfo]:
    """
    Recursively scan a directory for video files and return their metadata.

    Args:
        directory:  Root directory to scan.
        extensions: Set of lowercase extensions to include.
        recursive:  Scan subdirectories when True (default).
        progress_callback: Optional callback invoked after each inspected file
            with the current index, total file count, and file path.

    Returns:
        List of VideoInfo objects, one per discovered file.
    """
    if not directory.is_dir():
        raise NotADirectoryError(f"Not a directory: {directory}")

    pattern = "**/*" if recursive else "*"
    files = sorted(
        f for f in directory.glob(pattern)
        if f.is_file() and f.suffix.lower() in extensions
    )

    logger.info("Found %d video file(s) in %s", len(files), directory)

    results: list[VideoInfo] = []
    for idx, f in enumerate(files, start=1):
        logger.info("[%d/%d] Inspecting: %s", idx, len(files), f.name)
        results.append(inspect_file(f))
        if progress_callback is not None:
            progress_callback(idx, len(files), f)

    return results


# ---------------------------------------------------------------------------
# CSV export
# ---------------------------------------------------------------------------

# Column headers for the CSV — maps VideoInfo field names to display labels
_CSV_COLUMNS: dict[str, str] = {
    "file_name":            "Dateiname",
    "file_path":            "Pfad",
    "extension":            "Typ",
    "size_gb":              "Dateigröße (GB)",
    "duration":             "Dauer",
    "video_codec":          "Video-Codec",
    "resolution":           "Auflösung",
    "fps":                  "FPS",
    "audio_track_count":    "Audiospuren",
    "audio_languages":      "Audiosprachen",
    "subtitle_track_count": "Untertitelspuren",
    "subtitle_languages":   "Untertitelsprachen",
}


def export_to_csv(
    videos: list[VideoInfo],
    output_path: Path,
    delimiter: str = ";",
) -> None:
    """
    Export a list of VideoInfo objects to a CSV file.

    Uses semicolon as default delimiter to match the original PS export
    and be compatible with European Excel locales.

    Args:
        videos:      List of VideoInfo objects to export.
        output_path: Destination .csv file path.
        delimiter:   Field separator character. Defaults to ";".
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", newline="", encoding="utf-8-sig") as fh:
        # utf-8-sig writes the BOM so Excel opens it correctly
        writer = csv.DictWriter(
            fh,
            fieldnames=list(_CSV_COLUMNS.keys()),
            delimiter=delimiter,
            extrasaction="ignore",
        )

        # Write human-readable header row
        writer.writerow(_CSV_COLUMNS)

        for v in videos:
            row = asdict(v)
            writer.writerow(row)

    logger.info("CSV exported: %s (%d rows)", output_path, len(videos))
