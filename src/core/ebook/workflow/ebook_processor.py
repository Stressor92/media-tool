from __future__ import annotations

from pathlib import Path
import logging
from typing import Protocol

from core.ebook.cover.providers.provider import CoverImage
from core.ebook.models import BookIdentity
from core.ebook.models import BookMetadata, ProcessingResult
from core.ebook.normalization import NormalizationResult
from core.ebook.organization import LibraryOrganizer

logger = logging.getLogger(__name__)


class SupportsBookIdentifier(Protocol):
    def identify(self, file_path: Path) -> BookIdentity: ...


class SupportsMetadataService(Protocol):
    def fetch_metadata(self, book_identity: BookIdentity) -> BookMetadata | None: ...


class SupportsCoverService(Protocol):
    def get_cover(self, metadata: BookMetadata, min_resolution: int | None = None) -> CoverImage | None: ...


class SupportsNormalizer(Protocol):
    def normalize(
        self,
        epub_path: Path,
        metadata: BookMetadata | None = None,
        cover: CoverImage | None = None,
        fix_toc: bool = True,
        backup: bool = True,
    ) -> NormalizationResult: ...


class EbookProcessor:
    """Orchestrates identification, enrichment, conversion, and organization workflows."""

    def __init__(
        self,
        book_identifier: SupportsBookIdentifier,
        metadata_service: SupportsMetadataService,
        cover_service: SupportsCoverService,
        normalizer: SupportsNormalizer,
        converter: object | None = None,
        organizer: LibraryOrganizer | None = None,
    ) -> None:
        self.identifier = book_identifier
        self.metadata_service = metadata_service
        self.cover_service = cover_service
        self.normalizer = normalizer
        self.converter = converter
        self.organizer = organizer

    def enrich(
        self,
        ebook_path: Path,
        fetch_metadata: bool = True,
        fetch_cover: bool = True,
        normalize: bool = True,
        embed_metadata: bool = True,
        embed_cover: bool = True,
        dry_run: bool = False,
    ) -> ProcessingResult:
        result = ProcessingResult(ebook_path=ebook_path, success=False)

        if not ebook_path.exists() or not ebook_path.is_file():
            result.error_message = f"Input file not found: {ebook_path}"
            return result

        try:
            identity = self.identifier.identify(ebook_path)
            result.identified = True

            metadata = None
            if fetch_metadata:
                metadata = self.metadata_service.fetch_metadata(identity)
                result.metadata_fetched = metadata is not None

            cover = None
            if fetch_cover and metadata is not None:
                cover = self.cover_service.get_cover(metadata)
                result.cover_downloaded = cover is not None

            if dry_run:
                result.success = True
                result.final_path = ebook_path
                return result

            if normalize and metadata is not None:
                normalized = self.normalizer.normalize(
                    ebook_path,
                    metadata=metadata if embed_metadata else None,
                    cover=cover if embed_cover else None,
                    fix_toc=True,
                    backup=True,
                )
                result.normalized = normalized.success

            result.success = result.identified and (result.metadata_fetched or result.cover_downloaded or result.normalized)
            result.final_path = ebook_path
            return result
        except Exception as exc:
            logger.error("Ebook enrichment failed", extra={"path": str(ebook_path), "error": str(exc)})
            result.error_message = str(exc)
            return result

    def organize_library(
        self,
        source_path: Path,
        library_root: Path,
        fetch_metadata: bool = True,
        copy_instead_of_move: bool = False,
        dry_run: bool = False,
        recursive: bool = True,
    ) -> list[ProcessingResult]:
        if self.organizer is None:
            raise ValueError("LibraryOrganizer not configured")

        effective_organizer = self.organizer
        if dry_run:
            effective_organizer = self.organizer.__class__(self.organizer.naming, dry_run=True)

        files = self._scan_files(source_path, recursive=recursive)
        results: list[ProcessingResult] = []

        for ebook_path in files:
            result = ProcessingResult(ebook_path=ebook_path, success=False)
            try:
                identity = self.identifier.identify(ebook_path)
                result.identified = True

                metadata = self.metadata_service.fetch_metadata(identity) if fetch_metadata else None
                result.metadata_fetched = metadata is not None

                if metadata is None:
                    metadata = BookMetadata(title=identity.title, author=identity.author, isbn=identity.isbn, isbn13=identity.isbn13)

                org_result = effective_organizer.organize(
                    ebook_path,
                    metadata,
                    library_root,
                    copy_instead_of_move=copy_instead_of_move,
                    overwrite=False,
                )

                result.organized = org_result.success
                result.final_path = org_result.new_path
                result.success = org_result.success
                if not org_result.success:
                    result.error_message = org_result.error_message
            except Exception as exc:
                result.error_message = str(exc)
            results.append(result)

        return results

    def _scan_files(self, source_path: Path, recursive: bool) -> list[Path]:
        if not source_path.exists():
            return []

        extensions = {".epub", ".mobi", ".azw3", ".azw", ".pdf"}
        if source_path.is_file() and source_path.suffix.lower() in extensions:
            return [source_path]

        pattern = "**/*" if recursive else "*"
        return sorted([path for path in source_path.glob(pattern) if path.is_file() and path.suffix.lower() in extensions])
