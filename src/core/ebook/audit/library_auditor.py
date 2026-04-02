from __future__ import annotations

import logging
import zipfile
from collections import Counter
from pathlib import Path
from typing import Protocol

from core.ebook.audit.quality_checker import QualityChecker
from core.ebook.audit.series_analyzer import SeriesAnalyzer
from core.ebook.models import AuditReport, BookIdentity, BookMetadata

logger = logging.getLogger(__name__)


class SupportsBookIdentifier(Protocol):
    def identify(self, file_path: Path) -> BookIdentity: ...


class SupportsMetadataService(Protocol):
    def fetch_metadata(self, book_identity: BookIdentity) -> BookMetadata | None: ...


class SupportsIsbnExtractor(Protocol):
    def extract(self, file_path: Path) -> str | None: ...


class SupportsEpubReader(Protocol):
    def get_metadata(self, epub_path: Path) -> dict[str, str | None]: ...


class LibraryAuditor:
    """Comprehensive analysis for ebook library quality and consistency."""

    def __init__(
        self,
        book_identifier: SupportsBookIdentifier,
        metadata_service: SupportsMetadataService,
        isbn_extractor: SupportsIsbnExtractor,
        epub_reader: SupportsEpubReader,
        quality_checker: QualityChecker | None = None,
        series_analyzer: SeriesAnalyzer | None = None,
    ) -> None:
        self.identifier = book_identifier
        self.metadata_service = metadata_service
        self.isbn_extractor = isbn_extractor
        self.epub_reader = epub_reader
        self.quality_checker = quality_checker or QualityChecker()
        self.series_analyzer = series_analyzer or SeriesAnalyzer()

    def audit(
        self,
        library_path: Path,
        recursive: bool = True,
        check_covers: bool = True,
        check_series: bool = True,
    ) -> AuditReport:
        ebooks = self._scan_library(library_path, recursive)
        report = AuditReport(
            total_books=len(ebooks),
            total_size_gb=sum(path.stat().st_size for path in ebooks) / (1024**3) if ebooks else 0.0,
        )

        format_counts: Counter[str] = Counter()
        completeness_scores: list[float] = []
        series_entries: list[tuple[str, float | None]] = []

        for ebook_path in ebooks:
            format_counts[ebook_path.suffix.lower()] += 1

            quality_issue = self.quality_checker.check_format(ebook_path)
            if quality_issue is not None:
                report.format_issues.append((ebook_path, quality_issue))

            try:
                identity = self.identifier.identify(ebook_path)
            except Exception as exc:
                logger.error("Book identification failed", extra={"path": str(ebook_path), "error": str(exc)})
                report.broken_files.append(ebook_path)
                continue

            identity_issue = self.quality_checker.check_identity(identity)
            if identity_issue is not None:
                report.format_issues.append((ebook_path, identity_issue))

            if not (identity.isbn or identity.isbn13):
                extracted = self.isbn_extractor.extract(ebook_path)
                if extracted is None:
                    report.missing_isbn.append(ebook_path)

            metadata = self.metadata_service.fetch_metadata(identity)
            if metadata is None:
                report.missing_metadata.append(ebook_path)
            else:
                score = self.quality_checker.metadata_completeness(metadata)
                completeness_scores.append(score)
                if metadata.series:
                    series_entries.append((metadata.series, metadata.series_index))

            if check_covers and not self._has_cover(ebook_path):
                report.missing_cover.append(ebook_path)

        report.format_distribution = dict(format_counts)
        report.metadata_completeness = (
            (sum(completeness_scores) / len(completeness_scores)) if completeness_scores else 0.0
        )

        if check_series:
            grouped = self.series_analyzer.group(series_entries)
            report.series_gaps = self.series_analyzer.find_gaps(grouped)
            report.incomplete_series = self.series_analyzer.find_incomplete(grouped)

        return report

    def _scan_library(self, root_path: Path, recursive: bool) -> list[Path]:
        if not root_path.exists():
            return []
        pattern = "**/*" if recursive else "*"
        extensions = {".epub", ".mobi", ".azw3", ".pdf", ".azw"}
        return sorted(
            [path for path in root_path.glob(pattern) if path.is_file() and path.suffix.lower() in extensions]
        )

    def _has_cover(self, ebook_path: Path) -> bool:
        external = [
            ebook_path.parent / "cover.jpg",
            ebook_path.parent / "cover.jpeg",
            ebook_path.parent / "cover.png",
            ebook_path.with_suffix(".jpg"),
            ebook_path.with_suffix(".jpeg"),
            ebook_path.with_suffix(".png"),
        ]
        if any(path.exists() for path in external):
            return True

        if ebook_path.suffix.lower() != ".epub":
            return False

        try:
            with zipfile.ZipFile(ebook_path, "r") as archive:
                for name in archive.namelist():
                    lower = name.lower()
                    if "cover" in lower and lower.endswith((".jpg", ".jpeg", ".png", ".webp")):
                        return True
        except Exception:
            return False

        return False
