from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any


class PdfReadError(Exception):
    """Raised when PDF metadata or text cannot be read."""


class PdfReader:
    """Thin optional wrapper around pypdf for metadata and text extraction."""

    def get_metadata(self, file_path: Path) -> dict[str, str | None]:
        """Return normalized document metadata when pypdf is available."""
        reader = self._open_reader(file_path)
        raw_metadata = getattr(reader, "metadata", None)
        if raw_metadata is None:
            return {}

        result: dict[str, str | None] = {}
        for key, value in dict(raw_metadata).items():
            normalized_key = str(key).lstrip("/")
            result[normalized_key] = str(value) if value is not None else None
        return result

    def extract_text(self, file_path: Path, max_pages: int = 3) -> str:
        """Extract text from the first few pages when pypdf is available."""
        reader = self._open_reader(file_path)
        texts: list[str] = []
        page_count = min(max_pages, len(reader.pages))
        for page_index in range(page_count):
            extracted = reader.pages[page_index].extract_text() or ""
            texts.append(extracted)
        return "\n".join(texts)

    def _open_reader(self, file_path: Path) -> Any:
        try:
            module = importlib.import_module("pypdf")
            pdf_reader_class = getattr(module, "PdfReader")
        except ImportError as exc:
            raise PdfReadError("pypdf is required for PDF ebook inspection") from exc

        try:
            return pdf_reader_class(str(file_path))
        except Exception as exc:
            raise PdfReadError(f"Failed to read PDF: {exc}") from exc