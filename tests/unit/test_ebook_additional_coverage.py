from __future__ import annotations

from pathlib import Path
from typing import cast

from core.ebook.conversion.format_converter import FormatConverter
from core.ebook.deduplication.fingerprint_service import FingerprintService
from core.ebook.models import BookIdentity, BookMetadata, EbookFormat
from core.ebook.organization.naming_service import NamingService
from core.ebook.workflow.ebook_processor import EbookProcessor
from utils.calibre_runner import CalibreRunner


class _Runner:
    def convert(self, input_path: Path, output_path: Path, extra_args=None, timeout: int = 600):
        output_path.write_bytes(b"out")
        return None


class _BookIdentifier:
    def identify(self, file_path: Path) -> BookIdentity:
        return BookIdentity(title="Title", author="Author")


class _MetadataService:
    def fetch_metadata(self, book_identity: BookIdentity) -> BookMetadata | None:
        return None


class _CoverService:
    def get_cover(self, metadata: BookMetadata, min_resolution: int | None = None):
        return None


class _Normalizer:
    def normalize(self, epub_path: Path, metadata=None, cover=None, fix_toc: bool = True, backup: bool = True):
        class _Result:
            success = True

        return _Result()


def test_format_converter_rejects_invalid_cases(tmp_path: Path) -> None:
    converter = FormatConverter(cast(CalibreRunner, _Runner()), dry_run=True)

    missing = converter.convert(tmp_path / "missing.epub", EbookFormat.MOBI)
    assert missing.success is False

    source = tmp_path / "book.epub"
    source.write_bytes(b"x")
    same = converter.convert(source, EbookFormat.EPUB)
    assert same.success is False


def test_naming_service_series_format_and_truncate() -> None:
    long_name = "a" * 300
    cleaned = NamingService.sanitize_filename(long_name, max_length=20)
    assert len(cleaned) <= 20
    assert NamingService.format_series_name("Saga", 2.0) == "Saga #2"
    assert NamingService.format_series_name("Saga", 2.5) == "Saga #2.5"


def test_fingerprint_service_returns_hash(tmp_path: Path) -> None:
    file_path = tmp_path / "book.epub"
    file_path.write_bytes(b"12345")
    fp = FingerprintService().fingerprint(file_path)
    assert len(fp) == 64


def test_processor_enrich_handles_missing_input(tmp_path: Path) -> None:
    processor = EbookProcessor(
        book_identifier=_BookIdentifier(),
        metadata_service=_MetadataService(),
        cover_service=_CoverService(),
        normalizer=_Normalizer(),
    )
    result = processor.enrich(tmp_path / "missing.epub")
    assert result.success is False
    assert result.error_message is not None
