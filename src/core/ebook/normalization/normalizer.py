from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from core.ebook.cover.cover_service import CoverService
from core.ebook.cover.providers.provider import CoverImage
from core.ebook.models import BookMetadata
from core.ebook.normalization.epub_validator import EpubValidator
from core.ebook.normalization.metadata_embedder import MetadataEmbedder
from core.ebook.normalization.toc_generator import TocGenerator

logger = logging.getLogger(__name__)


@dataclass
class NormalizationResult:
    """Aggregated result of an EPUB normalization run."""

    success: bool
    metadata_updated: bool = False
    cover_embedded: bool = False
    toc_generated: bool = False
    structure_fixed: bool = False
    error_message: str | None = None


class EbookNormalizer:
    """Run metadata, cover, TOC, and validation steps for one EPUB."""

    def __init__(
        self,
        metadata_embedder: MetadataEmbedder,
        cover_service: CoverService,
        toc_generator: TocGenerator,
        epub_validator: EpubValidator,
    ) -> None:
        self.metadata_embedder = metadata_embedder
        self.cover_service = cover_service
        self.toc_generator = toc_generator
        self.validator = epub_validator

    def normalize(
        self,
        epub_path: Path,
        metadata: BookMetadata | None = None,
        cover: CoverImage | None = None,
        fix_toc: bool = True,
        backup: bool = True,
    ) -> NormalizationResult:
        """Apply available normalization steps to one EPUB file."""
        result = NormalizationResult(success=False)

        try:
            if not self.validator.is_valid(epub_path):
                result.error_message = "EPUB validation failed"
                return result

            if metadata is not None:
                result.metadata_updated = self.metadata_embedder.embed(epub_path, metadata, backup=backup)
            if cover is not None:
                result.cover_embedded = self.cover_service.embed_cover(epub_path, cover, backup=False)
            if fix_toc:
                result.toc_generated = self.toc_generator.generate(epub_path)

            result.success = any([result.metadata_updated, result.cover_embedded, result.toc_generated])
            result.structure_fixed = result.toc_generated
            return result
        except Exception as exc:
            logger.error("Ebook normalization failed", extra={"file_path": str(epub_path), "error": str(exc)})
            result.error_message = str(exc)
            return result
