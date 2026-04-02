from __future__ import annotations

from pathlib import Path
from typing import Any

from core.ebook.cover.providers.provider import CoverImage
from core.ebook.models import BookIdentity, BookMetadata
from core.ebook.organization import LibraryOrganizer
from core.ebook.organization.naming_service import NamingService
from core.ebook.workflow.ebook_processor import EbookProcessor


class _Identifier:
    def identify(self, file_path: Path) -> BookIdentity:
        return BookIdentity(title="Dune", author="Frank Herbert", isbn="9780441172719", isbn13="9780441172719", confidence_score=0.9)


class _MetadataService:
    def fetch_metadata(self, identity: BookIdentity) -> BookMetadata | None:
        return BookMetadata(title=identity.title, author=identity.author, isbn=identity.isbn, isbn13=identity.isbn13, source="test")


class _CoverService:
    def get_cover(self, metadata: BookMetadata, min_resolution: int | None = None) -> CoverImage | None:
        return None


class _NormalizationResult:
    success = True


class _Normalizer:
    def normalize(
        self,
        epub_path: Path,
        metadata: BookMetadata | None = None,
        cover: CoverImage | None = None,
        fix_toc: bool = True,
        backup: bool = True,
    ) -> Any:
        return _NormalizationResult()


class _BrokenIdentifier:
    def identify(self, file_path: Path) -> BookIdentity:
        raise RuntimeError("boom")


def test_processor_enrich_dry_run(tmp_path: Path) -> None:
    ebook = tmp_path / "book.epub"
    ebook.write_text("x", encoding="utf-8")

    processor = EbookProcessor(
        book_identifier=_Identifier(),
        metadata_service=_MetadataService(),
        cover_service=_CoverService(),
        normalizer=_Normalizer(),
    )

    result = processor.enrich(ebook, dry_run=True)

    assert result.success is True
    assert result.identified is True
    assert result.metadata_fetched is True
    assert result.cover_downloaded is True


def test_processor_organize_library(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    ebook = source / "book.epub"
    ebook.write_text("x", encoding="utf-8")

    library = tmp_path / "library"
    processor = EbookProcessor(
        book_identifier=_Identifier(),
        metadata_service=_MetadataService(),
        cover_service=_CoverService(),
        normalizer=_Normalizer(),
        organizer=LibraryOrganizer(naming_service=NamingService(), dry_run=False),
    )

    results = processor.organize_library(source, library, fetch_metadata=True, dry_run=False)

    assert len(results) == 1
    assert results[0].success is True
    assert results[0].organized is True
    assert results[0].final_path is not None
    assert results[0].final_path.exists()


def test_processor_enrich_exception_path(tmp_path: Path) -> None:
    ebook = tmp_path / "book.epub"
    ebook.write_text("x", encoding="utf-8")

    processor = EbookProcessor(
        book_identifier=_BrokenIdentifier(),
        metadata_service=_MetadataService(),
        cover_service=_CoverService(),
        normalizer=_Normalizer(),
    )

    result = processor.enrich(ebook, dry_run=False)

    assert result.success is False
    assert result.error_message is not None
