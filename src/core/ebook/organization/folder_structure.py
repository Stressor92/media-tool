from __future__ import annotations

from pathlib import Path

from core.ebook.models import BookMetadata, LibraryStructure
from core.ebook.organization.naming_service import NamingService


class FolderStructureBuilder:
    """Build `LibraryStructure` from metadata using shared naming utilities."""

    def __init__(self, naming_service: NamingService) -> None:
        self.naming = naming_service

    def build(self, metadata: BookMetadata, library_root: Path) -> LibraryStructure:
        author = metadata.author if metadata.author.strip() else "Unknown"
        title = metadata.title if metadata.title.strip() else "Unknown"
        series = metadata.series.strip() if metadata.series else None

        return LibraryStructure(
            root_path=library_root,
            author=self.naming.sanitize_filename(author),
            series=self.naming.sanitize_filename(series) if series else None,
            series_index=metadata.series_index,
            book_title=self.naming.sanitize_filename(title),
            year=metadata.published_year,
        )
