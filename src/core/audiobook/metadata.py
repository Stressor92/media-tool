"""
src/core/audiobook/metadata.py

Audiobook metadata extraction and enhancement.
"""

from __future__ import annotations

import logging
from pathlib import Path

from ..audio.metadata import AudioMetadataEnhanced, extract_audio_metadata_enhanced

logger = logging.getLogger(__name__)


def extract_audiobook_metadata_enhanced(file_path: Path) -> AudioMetadataEnhanced | None:
    """
    Extract enhanced metadata from audiobook files.

    This is a wrapper around the general audio metadata extraction,
    with audiobook-specific enhancements.

    Args:
        file_path: Path to the audiobook file.

    Returns:
        Enhanced metadata object or None if extraction failed.
    """
    metadata = extract_audio_metadata_enhanced(file_path)
    if not metadata:
        return None

    # Audiobook-specific enhancements
    # For audiobooks, we might want to prioritize narrator over artist
    # or look for series information in comments/tags

    # If we have a narrator field, use it as the primary author
    if metadata.narrator:
        # Keep the original artist but prioritize narrator for organization
        pass

    # Look for series information in various fields
    if not metadata.series:
        # Check if series info is in comments or other fields
        if metadata.comment:
            # Simple heuristic: look for "Book X of Y" or "Series: Name"
            comment_lower = metadata.comment.lower()
            if "book" in comment_lower and "of" in comment_lower:
                # Try to extract series info
                pass

    return metadata


def scan_audiobook_library(directory: Path, recursive: bool = True) -> list[AudioMetadataEnhanced]:
    """
    Scan a directory for audiobook files and extract metadata.

    Args:
        directory: Directory to scan.
        recursive: Whether to scan subdirectories.

    Returns:
        List of metadata objects for found audiobook files.
    """
    metadata_list = []

    # Common audiobook file extensions (includes .m4b which is standard for protected audiobooks)
    extensions = {".mp3", ".flac", ".m4a", ".m4b", ".aac", ".ogg", ".wma"}

    for ext in extensions:
        pattern = f"**/*{ext}" if recursive else f"*{ext}"
        for file_path in directory.glob(pattern):
            if file_path.is_file():
                metadata = extract_audiobook_metadata_enhanced(file_path)
                if metadata:
                    metadata_list.append(metadata)
                else:
                    logger.warning("Failed to extract metadata from: %s", file_path)

    return metadata_list
