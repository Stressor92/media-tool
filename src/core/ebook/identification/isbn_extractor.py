from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Protocol

logger = logging.getLogger(__name__)


class SupportsEpubMetadata(Protocol):
    def get_metadata(self, epub_path: Path) -> dict[str, str | None]: ...


class SupportsPdfReader(Protocol):
    def get_metadata(self, file_path: Path) -> dict[str, str | None]: ...

    def extract_text(self, file_path: Path, max_pages: int = 3) -> str: ...


class ISBNExtractor:
    """Extract and normalize ISBN identifiers from ebook files."""

    ISBN_PATTERN = re.compile(
        r"(?:ISBN(?:-1[03])?:?\s*)?(?P<isbn>(?:97[89][-\s]?)?(?:\d[-\s]?){9}[\dXx])",
        re.IGNORECASE,
    )

    def __init__(
        self,
        epub_reader: SupportsEpubMetadata,
        pdf_reader: SupportsPdfReader | None = None,
    ) -> None:
        self.epub_reader = epub_reader
        self.pdf_reader = pdf_reader

    def extract(self, file_path: Path) -> str | None:
        """Extract the first valid ISBN from a supported ebook file."""
        extension = file_path.suffix.lower()

        if extension == ".epub":
            return self._extract_from_epub(file_path)
        if extension == ".pdf" and self.pdf_reader is not None:
            return self._extract_from_pdf(file_path)

        logger.debug("Unsupported format for ISBN extraction", extra={"extension": extension})
        return None

    def _extract_from_epub(self, file_path: Path) -> str | None:
        try:
            metadata = self.epub_reader.get_metadata(file_path)
        except Exception as exc:
            logger.debug(
                "Failed to extract ISBN from EPUB",
                extra={"context": {"file_path": str(file_path), "error": str(exc)}},
            )
            return None

        candidates = [
            metadata.get("identifier"),
            metadata.get("isbn"),
            metadata.get("isbn13"),
            metadata.get("description"),
        ]
        return self._first_valid_isbn(candidates)

    def _extract_from_pdf(self, file_path: Path) -> str | None:
        if self.pdf_reader is None:
            return None

        try:
            metadata = self.pdf_reader.get_metadata(file_path)
            candidates = [
                metadata.get("ISBN"),
                metadata.get("isbn"),
                metadata.get("Subject"),
                metadata.get("Keywords"),
                self.pdf_reader.extract_text(file_path, max_pages=3),
            ]
            return self._first_valid_isbn(candidates)
        except Exception as exc:
            logger.debug(
                "Failed to extract ISBN from PDF",
                extra={"context": {"file_path": str(file_path), "error": str(exc)}},
            )
            return None

    def _first_valid_isbn(self, candidates: list[str | None]) -> str | None:
        for candidate in candidates:
            if not candidate:
                continue
            extracted = self._extract_candidate(candidate)
            if extracted is not None:
                return extracted
        return None

    def _extract_candidate(self, text: str) -> str | None:
        for match in self.ISBN_PATTERN.finditer(text):
            isbn = self._normalize_isbn(match.group("isbn"))
            if self._validate_isbn(isbn):
                return isbn
        return None

    def _normalize_isbn(self, isbn: str) -> str:
        cleaned = re.sub(r"[^\dXx]", "", isbn).upper()
        if len(cleaned) == 10:
            return self._isbn10_to_isbn13(cleaned)
        return cleaned

    def _isbn10_to_isbn13(self, isbn10: str) -> str:
        base = f"978{isbn10[:-1]}"
        check_sum = sum(int(digit) * (3 if index % 2 else 1) for index, digit in enumerate(base))
        check_digit = (10 - (check_sum % 10)) % 10
        return f"{base}{check_digit}"

    def _validate_isbn(self, isbn: str) -> bool:
        if len(isbn) == 13:
            return self._validate_isbn13(isbn)
        if len(isbn) == 10:
            return self._validate_isbn10(isbn)
        return False

    def _validate_isbn13(self, isbn: str) -> bool:
        if len(isbn) != 13 or not isbn.isdigit():
            return False

        check_sum = sum(int(digit) * (3 if index % 2 else 1) for index, digit in enumerate(isbn[:-1]))
        check_digit = (10 - (check_sum % 10)) % 10
        return check_digit == int(isbn[-1])

    def _validate_isbn10(self, isbn: str) -> bool:
        if len(isbn) != 10 or not re.fullmatch(r"\d{9}[\dX]", isbn):
            return False

        total = 0
        for index, char in enumerate(isbn):
            value = 10 if char == "X" else int(char)
            total += value * (10 - index)
        return total % 11 == 0
