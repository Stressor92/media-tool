"""
src/core/audiobook/organization.py

Audiobook library organization.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable
from pathlib import Path

from utils.progress import ProgressEvent, emit_progress

from ..audio.conversion import convert_audio
from ..audio.metadata import AudioMetadataEnhanced, extract_audio_metadata_enhanced

logger = logging.getLogger(__name__)

LANGUAGE_CODE_MAP = {
    "de": "de",
    "deu": "de",
    "ger": "de",
    "en": "en",
    "eng": "en",
}


def _sanitize_filename(name: str) -> str:
    """Sanitize filename by removing/replacing invalid characters."""
    import re

    # Replace invalid characters with underscores
    return re.sub(r'[<>:"/\\|?*]', "_", name)


def _normalize_language_label(language: str | None) -> str:
    """Normalize language tag values to short labels used in folder names."""
    if not language:
        return "de"

    # Handle values such as "deu", "ger", "en-US", or "de,en".
    raw_parts = re.split(r"[,;/|\\s]+", language)
    normalized: list[str] = []
    for part in raw_parts:
        token = part.strip().lower()
        if not token:
            continue
        token = token.split("-")[0]
        normalized_token = LANGUAGE_CODE_MAP.get(token, token)
        if normalized_token not in normalized:
            normalized.append(normalized_token)

    if not normalized:
        return "de"

    return "+".join(normalized)


def _generate_audiobook_path(metadata: AudioMetadataEnhanced, base_dir: Path, extension: str) -> Path:
    """
    Generate Jellyfin-compatible path for audiobook files.

    Structure: Audiobooks/Author-Title-Year-Language/Title.ext
    """
    # Build folder key from one hierarchy level as requested.
    author = metadata.narrator or metadata.artist or metadata.parsed_artist or "Unknown Author"
    book = metadata.album or metadata.parsed_album or metadata.series or "Unknown Title"
    title = metadata.title or metadata.parsed_title or metadata.filename
    year = str(metadata.year) if metadata.year else "unknown"
    language = _normalize_language_label(getattr(metadata, "language", None))

    # Sanitize
    author = _sanitize_filename(author)
    book = _sanitize_filename(book)
    title = _sanitize_filename(title)
    year = _sanitize_filename(year)
    language = _sanitize_filename(language)

    folder_name = f"{author}-{book}-{year}-{language}"

    filename = f"{title}.{extension}"

    return base_dir / "Audiobooks" / folder_name / filename


def organize_audiobooks(
    input_dir: Path,
    output_dir: Path,
    convert_format: str | None = "flac",
    recursive: bool = True,
    overwrite: bool = False,
    progress_callback: Callable[[ProgressEvent], None] | None = None,
) -> dict[str, int]:
    """
    Organize audiobook files into Jellyfin-compatible structure.

    Args:
        input_dir: Directory containing audiobook files.
        output_dir: Base directory for organized files.
        convert_format: Target format for conversion (None to skip conversion).
        recursive: Whether to search subdirectories.
        overwrite: Whether to overwrite existing files.

    Returns:
        Dict with counts: {"processed": int, "converted": int, "skipped": int, "errors": int}
    """
    if not input_dir.is_dir():
        raise NotADirectoryError(f"Input directory not found: {input_dir}")

    # Find audio files
    extensions = {".mp3", ".flac", ".m4a", ".m4b", ".aac", ".ogg", ".wma"}
    audio_files: list[Path] = []
    for ext in extensions:
        if recursive:
            audio_files.extend(input_dir.rglob(f"*{ext}"))
        else:
            audio_files.extend(input_dir.glob(f"*{ext}"))

    logger.info("Found %d audiobook files in %s", len(audio_files), input_dir)

    counts = {"processed": 0, "converted": 0, "skipped": 0, "errors": 0}
    total = len(audio_files)

    for index, input_file in enumerate(audio_files, start=1):
        emit_progress(
            progress_callback,
            ProgressEvent("organize-audiobook", index, total, input_file.name, "start", str(input_file)),
        )
        try:
            # Extract metadata
            metadata = extract_audio_metadata_enhanced(input_file)
            if not metadata:
                logger.warning("Could not extract metadata from %s", input_file)
                counts["errors"] += 1
                emit_progress(
                    progress_callback,
                    ProgressEvent(
                        "organize-audiobook", index, total, input_file.name, "failed", "Could not extract metadata"
                    ),
                )
                continue

            # Generate target path
            target_extension = convert_format or input_file.suffix.lower().lstrip(".")
            target_path = _generate_audiobook_path(metadata, output_dir, target_extension)

            # Check if target exists
            if target_path.exists() and not overwrite:
                logger.info("Skipping (exists): %s", target_path)
                counts["skipped"] += 1
                emit_progress(
                    progress_callback,
                    ProgressEvent(
                        "organize-audiobook",
                        index,
                        total,
                        input_file.name,
                        "skipped",
                        f"Target exists: {target_path.name}",
                    ),
                )
                continue

            # Convert if needed
            if convert_format and input_file.suffix.lower() != f".{convert_format}":
                result = convert_audio(
                    input_file=input_file,
                    output_file=target_path,
                    format=convert_format,
                    preserve_metadata=True,
                    overwrite=overwrite,
                )
                if result.success:
                    logger.info("Converted and organized: %s → %s", input_file, target_path)
                    counts["converted"] += 1
                    emit_progress(
                        progress_callback,
                        ProgressEvent(
                            "organize-audiobook",
                            index,
                            total,
                            input_file.name,
                            "success",
                            f"Converted to {target_path.name}",
                        ),
                    )
                else:
                    logger.error("Conversion failed: %s", input_file)
                    counts["errors"] += 1
                    emit_progress(
                        progress_callback,
                        ProgressEvent(
                            "organize-audiobook", index, total, input_file.name, "failed", "Conversion failed"
                        ),
                    )
            else:
                # Just copy
                target_path.parent.mkdir(parents=True, exist_ok=True)
                import shutil

                shutil.copy2(input_file, target_path)
                logger.info("Organized: %s → %s", input_file, target_path)
                counts["processed"] += 1
                emit_progress(
                    progress_callback,
                    ProgressEvent(
                        "organize-audiobook", index, total, input_file.name, "success", f"Copied to {target_path.name}"
                    ),
                )

        except Exception as e:
            logger.error("Error processing %s: %s", input_file, e)
            counts["errors"] += 1
            emit_progress(
                progress_callback,
                ProgressEvent("organize-audiobook", index, total, input_file.name, "failed", str(e)),
            )

    return counts


def organize_audiobooks_from_subfolders(
    input_root: Path,
    output_dir: Path,
    convert_format: str | None = "flac",
    overwrite: bool = False,
    progress_callback: Callable[[ProgressEvent], None] | None = None,
) -> dict[str, int]:
    """Collect audiobook files recursively from subfolders and organize into flat folder keys."""
    return organize_audiobooks(
        input_dir=input_root,
        output_dir=output_dir,
        convert_format=convert_format,
        recursive=True,
        overwrite=overwrite,
        progress_callback=progress_callback,
    )
