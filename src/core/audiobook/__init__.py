"""
src/core/audiobook/__init__.py

Audiobook processing core functionality.
"""

from .merger import detect_chapter_files, merge_audiobook_chapters, merge_audiobook_library
from .metadata import extract_audiobook_metadata_enhanced, scan_audiobook_library
from .organization import organize_audiobooks

__all__ = [
    "extract_audiobook_metadata_enhanced",
    "scan_audiobook_library",
    "organize_audiobooks",
    "detect_chapter_files",
    "merge_audiobook_chapters",
    "merge_audiobook_library",
]
