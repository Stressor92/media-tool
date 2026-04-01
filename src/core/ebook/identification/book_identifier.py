from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Protocol

from core.ebook.identification.confidence_scorer import ConfidenceScorer
from core.ebook.identification.isbn_extractor import ISBNExtractor
from core.ebook.models import BookIdentity

logger = logging.getLogger(__name__)


class SupportsMetadataReader(Protocol):
    def get_metadata(self, epub_path: Path) -> dict[str, str | None]: ...


class BookIdentifier:
    """Identify books using ISBN, embedded metadata, and filename heuristics."""

    def __init__(
        self,
        isbn_extractor: ISBNExtractor,
        epub_reader: SupportsMetadataReader,
    ) -> None:
        self.isbn_extractor = isbn_extractor
        self.epub_reader = epub_reader

    def identify(self, file_path: Path) -> BookIdentity:
        """Return the best available book identity for one ebook file."""
        isbn = self.isbn_extractor.extract(file_path)
        metadata = self._extract_metadata(file_path)

        title = self._clean_value(metadata.get("title"))
        author = self._clean_value(metadata.get("author"))

        if isbn is not None:
            return BookIdentity(
                title=title or file_path.stem,
                author=author or "Unknown",
                isbn=isbn,
                isbn13=isbn if len(isbn) == 13 else None,
                confidence_score=ConfidenceScorer.score_identity(
                    source="isbn",
                    has_isbn=True,
                    has_title=title is not None,
                    has_author=author is not None,
                ),
                source="isbn",
            )

        if title and author:
            return BookIdentity(
                title=title,
                author=author,
                confidence_score=ConfidenceScorer.score_identity(
                    source="metadata",
                    has_isbn=False,
                    has_title=True,
                    has_author=True,
                ),
                source="metadata",
            )

        parsed_title, parsed_author = self._parse_filename(file_path.stem)
        return BookIdentity(
            title=parsed_title,
            author=parsed_author or "Unknown",
            confidence_score=ConfidenceScorer.score_identity(
                source="filename",
                has_isbn=False,
                has_title=bool(parsed_title),
                has_author=parsed_author is not None,
            ),
            source="filename",
        )

    def _extract_metadata(self, file_path: Path) -> dict[str, str | None]:
        if file_path.suffix.lower() != ".epub":
            return {}

        try:
            return self.epub_reader.get_metadata(file_path)
        except Exception as exc:
            logger.error("Metadata extraction failed", extra={"file_path": str(file_path), "error": str(exc)})
            return {}

    @staticmethod
    def _clean_value(value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None

    @staticmethod
    def _parse_filename(filename: str) -> tuple[str, str | None]:
        match = re.match(r"^(.+?)\s*-\s*(.+)$", filename)
        if match:
            part1, part2 = match.groups()
            if BookIdentifier._looks_like_person_name(part1) and not BookIdentifier._looks_like_person_name(part2):
                return part2.strip(), part1.strip()
            if BookIdentifier._looks_like_person_name(part2) and not BookIdentifier._looks_like_person_name(part1):
                return part1.strip(), part2.strip()
            if len(part1) < len(part2):
                return part2.strip(), part1.strip()
            return part1.strip(), part2.strip()

        match = re.match(r"^(.+?)\s*\((.+?)\)$", filename)
        if match:
            title, author = match.groups()
            return title.strip(), author.strip()

        return filename, None

    @staticmethod
    def _looks_like_person_name(value: str) -> bool:
        return bool(re.fullmatch(r"[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3}", value.strip()))