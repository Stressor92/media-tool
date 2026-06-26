"""
src/core/audiobook/merger.py

Audiobook chapter merging functionality.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any, Literal, TypedDict

from src.backup import get_backup_manager
from src.backup.models import MediaType
from utils.progress import ProgressEvent, emit_progress

from .metadata import extract_audiobook_metadata_enhanced

logger = logging.getLogger(__name__)

GroupingStrategy = Literal["metadata-first", "filename"]


# Patterns for detecting chapter files
CHAPTER_PATTERNS = [
    # "Book Title - Chapter 01.mp3"
    re.compile(r"^(.+?)\s*-\s*Chapter\s+(\d+)", re.IGNORECASE),
    # "Book Title - Part 01.mp3"
    re.compile(r"^(.+?)\s*-\s*Part\s+(\d+)", re.IGNORECASE),
    # "Book Title 01.mp3"
    re.compile(r"^(.+?)\s+(\d+)(?:\.\w+)?$", re.IGNORECASE),
    # "Book Title - 01.mp3"
    re.compile(r"^(.+?)\s*-\s*(\d+)", re.IGNORECASE),
    # "01 - Book Title.mp3" (less common but possible)
    re.compile(r"^(\d+)\s*-\s*(.+)$", re.IGNORECASE),
]


class MergedBookInfo(TypedDict, total=False):
    title: str
    chapters: int
    output_file: str
    size_mb: float | None
    dry_run: bool


class MergeLibraryResult(TypedDict):
    books_found: int
    books_merged: int
    total_chapters: int
    merged_books: list[MergedBookInfo]
    errors: list[str]


def _extract_chapter_from_filename(filename_stem: str) -> tuple[str, int] | None:
    """Extract (book_title, chapter_number) from filename patterns."""
    for pattern in CHAPTER_PATTERNS:
        match = pattern.match(filename_stem)
        if not match:
            continue

        groups = match.groups()
        if pattern == CHAPTER_PATTERNS[-1]:
            chapter_str, book_title = groups
        else:
            book_title, chapter_str = groups

        try:
            chapter_num = int(chapter_str)
            if chapter_num <= 0:
                return None
        except ValueError:
            return None

        return _clean_book_title(book_title.strip()), chapter_num

    return None


def _metadata_group_title(metadata: Any | None) -> str | None:
    """Build grouping title from audiobook metadata."""
    if metadata is None:
        return None

    candidates = [
        getattr(metadata, "album", None),
        getattr(metadata, "series", None),
        getattr(metadata, "parsed_album", None),
    ]
    for candidate in candidates:
        if isinstance(candidate, str) and candidate.strip():
            return _clean_book_title(candidate.strip())

    return None


def _chapter_number_from_metadata_or_filename(metadata: Any | None, file_path: Path) -> int | None:
    """Resolve chapter number with metadata priority and filename fallback."""
    if metadata is not None:
        for field_name in ("track_number", "parsed_track_number"):
            value = getattr(metadata, field_name, None)
            if isinstance(value, int) and value > 0:
                return value

    from_name = _extract_chapter_from_filename(file_path.stem)
    if from_name:
        return from_name[1]

    return None


def _chapter_sort_key(metadata: Any | None, file_path: Path, chapter_num: int | None) -> tuple[int, int, int, str]:
    """Sort chapters deterministically for merge order."""
    stem = file_path.stem.casefold()

    if metadata is not None:
        disc_number = getattr(metadata, "disc_number", None)
        if not isinstance(disc_number, int) or disc_number <= 0:
            disc_number = 1

        track_number = getattr(metadata, "track_number", None)
        if isinstance(track_number, int) and track_number > 0:
            return (0, disc_number, track_number, stem)

        parsed_track_number = getattr(metadata, "parsed_track_number", None)
        if isinstance(parsed_track_number, int) and parsed_track_number > 0:
            return (1, disc_number, parsed_track_number, stem)

    if isinstance(chapter_num, int) and chapter_num > 0:
        return (2, 1, chapter_num, stem)

    # Stable lexical fallback for files without ordering hints.
    return (3, 1, 0, stem)


def detect_chapter_files(
    directory: Path,
    grouping_strategy: GroupingStrategy = "metadata-first",
    progress_callback: Callable[[ProgressEvent], None] | None = None,
) -> dict[str, list[tuple[Path, int]]]:
    """
    Detect and group chapter files by book title.

    Args:
        directory: Directory to scan for chapter files.

    Returns:
        Dict mapping book titles to lists of (file_path, chapter_number) tuples.
    """
    book_chapters_raw: dict[str, list[tuple[Path, tuple[int, int, int, str], int | None]]] = {}

    # Common audiobook extensions
    extensions = {".mp3", ".m4a", ".m4b", ".aac", ".ogg", ".flac"}

    candidate_files = [
        file_path
        for file_path in sorted(directory.rglob("*"), key=lambda p: str(p).casefold())
        if file_path.is_file() and file_path.suffix.lower() in extensions
    ]
    total_candidates = len(candidate_files)

    emit_progress(
        progress_callback,
        ProgressEvent(
            "scan-audiobook-chapters",
            0,
            total_candidates,
            "scan",
            "info",
            f"Scanning {total_candidates} audio files for chapter groups...",
        ),
    )

    for index, file_path in enumerate(candidate_files, start=1):
        if total_candidates <= 20 or index == 1 or index % 25 == 0 or index == total_candidates:
            emit_progress(
                progress_callback,
                ProgressEvent(
                    "scan-audiobook-chapters",
                    index,
                    total_candidates,
                    file_path.name,
                    "start",
                    file_path.name,
                ),
            )

        metadata = None
        if grouping_strategy == "metadata-first":
            try:
                metadata = extract_audiobook_metadata_enhanced(file_path)
            except Exception:
                logger.debug("Metadata extraction failed for %s", file_path, exc_info=True)

            metadata_title = _metadata_group_title(metadata)
            if metadata_title:
                chapter_num = _chapter_number_from_metadata_or_filename(metadata, file_path)
                sort_key = _chapter_sort_key(metadata, file_path, chapter_num)
                book_chapters_raw.setdefault(metadata_title, []).append((file_path, sort_key, chapter_num))
                continue

        detected = _extract_chapter_from_filename(file_path.stem)
        if detected is None:
            continue

        book_title, chapter_num = detected
        sort_key = _chapter_sort_key(None, file_path, chapter_num)
        book_chapters_raw.setdefault(book_title, []).append((file_path, sort_key, chapter_num))

    # Finalize chapter ordering per detected book.
    book_chapters: dict[str, list[tuple[Path, int]]] = {}
    for book_title, chapters in book_chapters_raw.items():
        ordered = sorted(chapters, key=lambda item: item[1])
        finalized: list[tuple[Path, int]] = []
        for index, (chapter_path, _, chapter_num) in enumerate(ordered, start=1):
            finalized.append((chapter_path, chapter_num if chapter_num is not None else index))
        book_chapters[book_title] = finalized

    emit_progress(
        progress_callback,
        ProgressEvent(
            "scan-audiobook-chapters",
            total_candidates,
            total_candidates,
            "scan",
            "info",
            f"Detected {len(book_chapters)} potential books from {total_candidates} files.",
        ),
    )

    return book_chapters


def _clean_book_title(title: str) -> str:
    """Clean and normalize book title for grouping."""
    # Remove common prefixes/suffixes that might interfere with grouping
    title = re.sub(r"\s+", " ", title)  # Normalize whitespace
    title = title.strip()

    # Remove trailing numbers that might be part of chapter detection
    title = re.sub(r"\s+\d+$", "", title)

    return title


def merge_audiobook_chapters(
    chapter_files: list[Path],
    output_file: Path,
    output_format: str | None = None,
    preserve_metadata: bool = True,
    overwrite: bool = False,
) -> dict[str, Any]:
    """
    Merge multiple audiobook chapter files into a single file.

    Args:
        chapter_files: List of chapter files in order.
        output_file: Output file path.
        preserve_metadata: Whether to preserve metadata from first file.
        overwrite: Whether to overwrite existing output file.

    Returns:
        Dict with merge results and statistics.
    """
    if not chapter_files:
        return {"success": False, "error": "No chapter files provided"}

    if output_file.exists() and not overwrite:
        return {"success": False, "error": f"Output file exists: {output_file}"}

    # Ensure output directory exists
    output_file.parent.mkdir(parents=True, exist_ok=True)

    resolved_format = (output_format or output_file.suffix.lstrip(".") or "m4a").lower()

    backup_entry = None
    if output_file.exists() and overwrite:
        try:
            backup_entry = get_backup_manager().create(
                output_file, operation="audiobook_merge", media_type=MediaType.AUDIOBOOK
            )
        except Exception:
            logger.debug("Backup creation failed", exc_info=True)

    # Create a temporary concat file list for ffmpeg
    concat_file = output_file.parent / f"{output_file.stem}_concat.txt"

    try:
        # Write concat file
        with open(concat_file, "w", encoding="utf-8") as f:
            for chapter_file in chapter_files:
                # Escape single quotes in filename for ffmpeg
                escaped_path = str(chapter_file).replace("'", "\\'")
                f.write(f"file '{escaped_path}'\n")

        # Build ffmpeg command for concatenation
        args = [
            "-f",
            "concat",
            "-safe",
            "0",  # Allow absolute paths
            "-i",
            str(concat_file),
            # Keep merge robust when chapter files contain mixed/unsupported side streams
            # (e.g., embedded cover MJPEG in MP3). Only write the primary audio stream.
            "-map",
            "0:a:0",
        ]

        codec_by_format = {
            "m4a": ["-c:a", "aac"],
            "m4b": ["-c:a", "aac"],
            "aac": ["-c:a", "aac"],
            "mp3": ["-c:a", "libmp3lame"],
            "flac": ["-c:a", "flac"],
            "ogg": ["-c:a", "libopus"],
            "opus": ["-c:a", "libopus"],
        }
        args.extend(codec_by_format.get(resolved_format, ["-c:a", "aac"]))

        if resolved_format in {"m4a", "m4b", "aac"}:
            args.extend(["-movflags", "+faststart"])

        if preserve_metadata:
            # Try to extract metadata from first file
            first_metadata = extract_audiobook_metadata_enhanced(chapter_files[0])
            if first_metadata:
                # Set basic metadata
                if first_metadata.title:
                    args.extend(["-metadata", f"title={first_metadata.title}"])
                if first_metadata.artist:
                    args.extend(["-metadata", f"artist={first_metadata.artist}"])
                if first_metadata.album:
                    args.extend(["-metadata", f"album={first_metadata.album}"])

        args.extend(["-y" if overwrite else "-n", str(output_file)])

        # Run ffmpeg
        from utils.ffmpeg_runner import run_ffmpeg

        result = run_ffmpeg(args)

        # Clean up concat file
        concat_file.unlink(missing_ok=True)

        if result.success:
            # Get final file size
            final_size = output_file.stat().st_size if output_file.exists() else 0

            return {
                "success": True,
                "output_file": output_file,
                "chapters_merged": len(chapter_files),
                "total_size": final_size,
                "ffmpeg_result": result,
            }
        else:
            # Clean up failed output file
            output_file.unlink(missing_ok=True)
            if backup_entry is not None:
                try:
                    get_backup_manager().rollback(backup_entry)
                except Exception:
                    logger.debug("Backup rollback failed", exc_info=True)
            return {
                "success": False,
                "error": f"FFmpeg failed: {result.stderr}",
                "ffmpeg_result": result,
            }

    except Exception as e:
        # Clean up
        concat_file.unlink(missing_ok=True)
        output_file.unlink(missing_ok=True)
        if backup_entry is not None:
            try:
                get_backup_manager().rollback(backup_entry)
            except Exception:
                logger.debug("Backup rollback failed", exc_info=True)
        return {"success": False, "error": str(e)}


def merge_audiobook_library(
    input_dir: Path,
    output_dir: Path,
    format: str = "m4a",
    grouping_strategy: GroupingStrategy = "metadata-first",
    overwrite: bool = False,
    dry_run: bool = False,
    progress_callback: Callable[[ProgressEvent], None] | None = None,
) -> MergeLibraryResult:
    """
    Scan a directory for chapter-based audiobooks and merge them.

    Args:
        input_dir: Directory containing chapter files.
        output_dir: Directory for merged audiobook files.
        format: Output format (m4a, m4b, mp3, flac, etc.).
        grouping_strategy: Chapter grouping strategy (metadata-first or filename).
        overwrite: Whether to overwrite existing files.

    Returns:
        Dict with merge statistics.
    """
    logger.info(f"Scanning {input_dir} for audiobook chapters...")

    emit_progress(
        progress_callback,
        ProgressEvent(
            "merge-audiobook",
            0,
            0,
            "merge",
            "info",
            f"Starting detection in {input_dir} with grouping '{grouping_strategy}'.",
        ),
    )

    # Detect chapter files
    book_chapters = detect_chapter_files(
        input_dir,
        grouping_strategy=grouping_strategy,
        progress_callback=progress_callback,
    )

    if not book_chapters:
        return {
            "books_found": 0,
            "books_merged": 0,
            "total_chapters": 0,
            "merged_books": [],
            "errors": ["No chapter files detected"],
        }

    logger.info(f"Found {len(book_chapters)} potential books with chapters")

    preview_titles = sorted(book_chapters.keys(), key=str.casefold)
    if preview_titles:
        preview_text = ", ".join(preview_titles[:8])
        if len(preview_titles) > 8:
            preview_text += f" ... (+{len(preview_titles) - 8} more)"
        emit_progress(
            progress_callback,
            ProgressEvent(
                "merge-audiobook",
                0,
                len(preview_titles),
                "books",
                "info",
                f"Books detected: {preview_text}",
            ),
        )

    results: MergeLibraryResult = {
        "books_found": len(book_chapters),
        "books_merged": 0,
        "total_chapters": sum(len(chapters) for chapters in book_chapters.values()),
        "merged_books": [],
        "errors": [],
    }
    total = len(book_chapters)

    # Process each book
    for index, (book_title, chapters) in enumerate(book_chapters.items(), start=1):
        emit_progress(
            progress_callback,
            ProgressEvent("merge-audiobook", index, total, book_title, "start", f"{len(chapters)} chapter(s)"),
        )
        if len(chapters) < 2:
            logger.info(f"Skipping '{book_title}' - only {len(chapters)} chapter(s)")
            emit_progress(
                progress_callback,
                ProgressEvent(
                    "merge-audiobook", index, total, book_title, "skipped", f"Only {len(chapters)} chapter(s)"
                ),
            )
            continue

        # Sort chapters by chapter number
        chapters.sort(key=lambda x: x[1])
        chapter_files = [chapter[0] for chapter in chapters]

        # Generate output filename
        safe_title = _sanitize_filename(book_title)
        output_file = output_dir / f"{safe_title}.{format}"

        logger.info(f"Merging '{book_title}' - {len(chapters)} chapters → {output_file.name}")

        if dry_run:
            # In dry run mode, do not perform actual merging.
            results["merged_books"].append(
                {
                    "title": book_title,
                    "chapters": len(chapters),
                    "output_file": str(output_file),
                    "size_mb": None,
                    "dry_run": True,
                }
            )
            logger.info(f"Dry run: would merge '{book_title}'")
            emit_progress(
                progress_callback,
                ProgressEvent("merge-audiobook", index, total, book_title, "success", "Dry run preview created"),
            )
            continue

        # Merge chapters
        merge_result = merge_audiobook_chapters(
            chapter_files=chapter_files,
            output_file=output_file,
            output_format=format,
            preserve_metadata=True,
            overwrite=overwrite,
        )

        if merge_result["success"]:
            results["books_merged"] += 1
            results["merged_books"].append(
                {
                    "title": book_title,
                    "chapters": len(chapters),
                    "output_file": str(output_file),
                    "size_mb": round(merge_result.get("total_size", 0) / 1_048_576, 2),
                }
            )
            logger.info(f"✓ Successfully merged '{book_title}'")
            emit_progress(
                progress_callback,
                ProgressEvent(
                    "merge-audiobook", index, total, book_title, "success", f"Merged {len(chapters)} chapters"
                ),
            )
        else:
            error_msg = f"Failed to merge '{book_title}': {merge_result.get('error', 'Unknown error')}"
            results["errors"].append(error_msg)
            logger.error(f"✗ {error_msg}")
            emit_progress(
                progress_callback,
                ProgressEvent("merge-audiobook", index, total, book_title, "failed", error_msg),
            )

    return results


def _sanitize_filename(name: str) -> str:
    """Sanitize filename by removing/replacing invalid characters."""
    import re

    # Replace invalid characters with underscores
    return re.sub(r'[<>:"/\\|?*]', "_", name)
