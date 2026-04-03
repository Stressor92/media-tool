"""
src/core/audiobook/merger.py

Audiobook chapter merging functionality.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any, TypedDict

from src.backup import get_backup_manager
from src.backup.models import MediaType

from utils.progress import ProgressEvent, emit_progress

from .metadata import extract_audiobook_metadata_enhanced

logger = logging.getLogger(__name__)


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


def detect_chapter_files(directory: Path) -> dict[str, list[tuple[Path, int]]]:
    """
    Detect and group chapter files by book title.

    Args:
        directory: Directory to scan for chapter files.

    Returns:
        Dict mapping book titles to lists of (file_path, chapter_number) tuples.
    """
    book_chapters: dict[str, list[tuple[Path, int]]] = {}

    # Common audiobook extensions
    extensions = {".mp3", ".m4a", ".aac", ".ogg", ".flac"}

    for file_path in directory.rglob("*"):
        if not file_path.is_file() or file_path.suffix.lower() not in extensions:
            continue

        filename = file_path.stem  # Remove extension

        for pattern in CHAPTER_PATTERNS:
            match = pattern.match(filename)
            if match:
                groups = match.groups()

                # Check if this is the "number first" pattern (last pattern in list)
                if pattern == CHAPTER_PATTERNS[-1]:  # "01 - Book Title" pattern
                    chapter_str, book_title = groups
                else:  # All other patterns: title first, then number
                    book_title, chapter_str = groups

                try:
                    chapter_num = int(chapter_str)
                    book_title = book_title.strip()
                except ValueError:
                    continue

                # Clean up book title
                book_title = _clean_book_title(book_title)

                if book_title not in book_chapters:
                    book_chapters[book_title] = []

                book_chapters[book_title].append((file_path, chapter_num))
                break  # Found a match, no need to check other patterns

    # Sort chapters by chapter number for each book
    for book_title in book_chapters:
        book_chapters[book_title].sort(key=lambda x: x[1])

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
            "-c",
            "copy",  # Copy streams without re-encoding
        ]

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
    overwrite: bool = False,
    dry_run: bool = False,
    progress_callback: Callable[[ProgressEvent], None] | None = None,
) -> MergeLibraryResult:
    """
    Scan a directory for chapter-based audiobooks and merge them.

    Args:
        input_dir: Directory containing chapter files.
        output_dir: Directory for merged audiobook files.
        format: Output format (m4a, mp3, flac, etc.).
        overwrite: Whether to overwrite existing files.

    Returns:
        Dict with merge statistics.
    """
    logger.info(f"Scanning {input_dir} for audiobook chapters...")

    # Detect chapter files
    book_chapters = detect_chapter_files(input_dir)

    if not book_chapters:
        return {
            "books_found": 0,
            "books_merged": 0,
            "total_chapters": 0,
            "merged_books": [],
            "errors": ["No chapter files detected"],
        }

    logger.info(f"Found {len(book_chapters)} potential books with chapters")

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
