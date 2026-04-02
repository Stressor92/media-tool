from __future__ import annotations

import logging
import shutil
from pathlib import Path

from core.ebook.models import BookMetadata
from utils.epub_writer import EpubWriter

logger = logging.getLogger(__name__)


class MetadataEmbedder:
    """Embed enriched metadata into EPUB package metadata."""

    def __init__(self, epub_writer: EpubWriter) -> None:
        self.epub_writer = epub_writer

    def embed(self, epub_path: Path, metadata: BookMetadata, backup: bool = True) -> bool:
        """Update an EPUB's OPF metadata fields from one BookMetadata object."""
        try:
            if backup:
                shutil.copy2(epub_path, epub_path.with_suffix(".epub.bak"))

            metadata_dict = {
                "title": metadata.title,
                "creator": metadata.author,
                "description": metadata.description,
                "publisher": metadata.publisher,
                "date": str(metadata.published_year) if metadata.published_year else None,
                "language": metadata.language,
                "identifier": metadata.isbn13 or metadata.isbn,
            }
            filtered = {key: value for key, value in metadata_dict.items() if value is not None}
            return self.epub_writer.update_metadata(epub_path, filtered)
        except Exception as exc:
            logger.error("Metadata embedding failed", extra={"file_path": str(epub_path), "error": str(exc)})
            return False
