from __future__ import annotations

from pathlib import Path

from utils.epub_writer import EpubWriter


class TocGenerator:
    """Generate a minimal navigation document when an EPUB lacks one."""

    def __init__(self, epub_writer: EpubWriter) -> None:
        self.epub_writer = epub_writer

    def generate(self, epub_path: Path) -> bool:
        """Ensure the EPUB contains a basic nav document and manifest entry."""
        return self.epub_writer.ensure_navigation(epub_path)