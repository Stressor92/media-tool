from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


@dataclass(frozen=True)
class BookIdentity:
    """Result of book identification."""

    title: str
    author: str
    isbn: str | None = None
    isbn13: str | None = None
    confidence_score: float = 0.0
    source: str = "unknown"

    def is_high_confidence(self) -> bool:
        """Return True when the identity score is strong enough for automation."""
        return self.confidence_score >= 0.8


@dataclass(frozen=True)
class BookMetadata:
    """Complete book metadata from one provider."""

    title: str
    author: str
    description: str | None = None
    language: str = "en"
    genres: list[str] = field(default_factory=list)
    publisher: str | None = None
    published_year: int | None = None
    isbn: str | None = None
    isbn13: str | None = None
    series: str | None = None
    series_index: float | None = None
    authors: list[str] = field(default_factory=list)
    page_count: int | None = None
    metadata_completeness: float = 0.0
    source: str = "unknown"

    def calculate_completeness(self) -> float:
        """Calculate a stable completeness score between 0.0 and 1.0."""
        score = 0.0
        score += 0.4

        if self.isbn or self.isbn13:
            score += 0.2
        if self.description and len(self.description.strip()) > 50:
            score += 0.15
        if self.publisher:
            score += 0.075
        if self.published_year is not None:
            score += 0.075
        if self.series:
            score += 0.05
        if self.genres:
            score += 0.05

        return round(score, 2)

    def with_calculated_completeness(self) -> BookMetadata:
        """Return a copy with metadata_completeness re-computed from current fields."""
        return BookMetadata(
            title=self.title,
            author=self.author,
            description=self.description,
            language=self.language,
            genres=list(self.genres),
            publisher=self.publisher,
            published_year=self.published_year,
            isbn=self.isbn,
            isbn13=self.isbn13,
            series=self.series,
            series_index=self.series_index,
            authors=list(self.authors),
            page_count=self.page_count,
            metadata_completeness=self.calculate_completeness(),
            source=self.source,
        )


class EbookFormat(Enum):
    """Supported e-book formats for conversion and organization flows."""

    EPUB = "epub"
    MOBI = "mobi"
    AZW3 = "azw3"
    PDF = "pdf"
    AZW = "azw"

    @classmethod
    def from_extension(cls, ext: str) -> EbookFormat | None:
        """Get format enum from a file extension like .epub or epub."""
        normalized = ext.lower().lstrip(".")
        try:
            return cls(normalized)
        except ValueError:
            return None


@dataclass(frozen=True)
class ConversionProfile:
    """Conversion quality profile for Calibre conversion runs."""

    name: str
    output_format: EbookFormat
    quality: str  # high | medium | low
    target_device: str | None = None
    compress_images: bool = True
    remove_drm: bool = False

    def to_calibre_args(self) -> list[str]:
        """Convert profile options into calibre CLI arguments."""
        args: list[str] = []

        quality = self.quality.strip().lower()
        if quality == "high":
            args.extend(["--extra-css", "body { text-align: justify; }"])
        elif quality == "low":
            args.append("--compress-images")

        if self.compress_images and "--compress-images" not in args:
            args.append("--compress-images")

        if self.target_device:
            args.extend(["--output-profile", self.target_device])

        return args


@dataclass(frozen=True)
class ConversionResult:
    """Result of one format conversion execution."""

    success: bool
    output_path: Path | None = None
    original_size_mb: float = 0.0
    output_size_mb: float = 0.0
    duration_seconds: float = 0.0
    error_message: str | None = None
    backup_path: Path | None = None
    dry_run: bool = False


@dataclass(frozen=True)
class DuplicateGroup:
    """A group of files determined to represent the same book."""

    books: list[Path]
    match_confidence: float
    best_version: Path
    reason: str


@dataclass(frozen=True)
class LibraryStructure:
    """Target folder and filename template for organized ebook storage."""

    root_path: Path
    author: str
    series: str | None = None
    series_index: float | None = None
    book_title: str = "Unknown"
    year: int | None = None

    @property
    def folder_path(self) -> Path:
        """Return the target folder path for this metadata payload."""
        author_name = self._sanitize_filename(self.author or "Unknown")
        title = self.filename

        if self.series:
            series_name = self._sanitize_filename(self.series)
            if self.series_index is not None:
                if self.series_index == int(self.series_index):
                    index = str(int(self.series_index))
                else:
                    index = str(self.series_index)
                series_name = self._sanitize_filename(f"{series_name} #{index}")
            return self.root_path / author_name / series_name / title

        return self.root_path / author_name / title

    @property
    def filename(self) -> str:
        """Return a sanitized filename stem for this book."""
        title = self.book_title.strip() or "Unknown"
        if self.year is not None:
            title = f"{title} ({self.year})"
        return self._sanitize_filename(title)

    @staticmethod
    def _sanitize_filename(name: str) -> str:
        import re

        cleaned = re.sub(r"[<>:\"/\\|?*]", "", name)
        cleaned = re.sub(r"\s+", " ", cleaned)
        cleaned = cleaned.strip(" .")
        return cleaned or "Unknown"


@dataclass
class AuditReport:
    """Complete library audit result for ebook collections."""

    total_books: int
    total_size_gb: float
    missing_metadata: list[Path] = field(default_factory=list)
    missing_cover: list[Path] = field(default_factory=list)
    missing_isbn: list[Path] = field(default_factory=list)
    format_issues: list[tuple[Path, str]] = field(default_factory=list)
    broken_files: list[Path] = field(default_factory=list)
    series_gaps: list[str] = field(default_factory=list)
    incomplete_series: list[str] = field(default_factory=list)
    format_distribution: dict[str, int] = field(default_factory=dict)
    metadata_completeness: float = 0.0

    def summary(self) -> str:
        """Generate a readable text summary for console or file output."""
        lines = [
            "Library Audit Report",
            "=" * 50,
            f"Total Books: {self.total_books}",
            f"Total Size: {self.total_size_gb:.2f} GB",
            "",
            "Issues:",
            f"  Missing Metadata: {len(self.missing_metadata)}",
            f"  Missing Cover: {len(self.missing_cover)}",
            f"  Missing ISBN: {len(self.missing_isbn)}",
            f"  Format Issues: {len(self.format_issues)}",
            f"  Broken Files: {len(self.broken_files)}",
            "",
            "Series:",
            f"  Gaps Detected: {len(self.series_gaps)}",
            f"  Incomplete: {len(self.incomplete_series)}",
            "",
            "Quality:",
            f"  Metadata Completeness: {self.metadata_completeness:.0%}",
        ]
        return "\n".join(lines)


@dataclass
class ProcessingResult:
    """Result of one end-to-end ebook workflow execution."""

    ebook_path: Path
    success: bool
    identified: bool = False
    metadata_fetched: bool = False
    cover_downloaded: bool = False
    normalized: bool = False
    converted: bool = False
    organized: bool = False
    final_path: Path | None = None
    cover_path: Path | None = None
    error_message: str | None = None

    @property
    def operations_completed(self) -> int:
        """Count successful operation flags."""
        return sum(
            [
                self.identified,
                self.metadata_fetched,
                self.cover_downloaded,
                self.normalized,
                self.converted,
                self.organized,
            ]
        )