from __future__ import annotations

import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from utils.epub_reader import EpubReader


@dataclass(frozen=True)
class ValidationResult:
    """Validation outcome for one EPUB file."""

    valid: bool
    errors: list[str] = field(default_factory=list)


class EpubValidator:
    """Minimal EPUB validation focused on archive and metadata integrity."""

    def __init__(self, epub_reader: EpubReader) -> None:
        self.epub_reader = epub_reader

    def validate(self, epub_path: Path) -> ValidationResult:
        """Validate ZIP structure, required container files, and readable metadata."""
        errors: list[str] = []
        try:
            with zipfile.ZipFile(epub_path, "r") as archive:
                names = set(archive.namelist())
                if "META-INF/container.xml" not in names:
                    errors.append("Missing META-INF/container.xml")
                if "mimetype" not in names:
                    errors.append("Missing mimetype file")
        except zipfile.BadZipFile:
            return ValidationResult(valid=False, errors=["Invalid ZIP archive"])
        except OSError as exc:
            return ValidationResult(valid=False, errors=[str(exc)])

        try:
            self.epub_reader.get_metadata(epub_path)
        except Exception as exc:
            errors.append(str(exc))

        return ValidationResult(valid=not errors, errors=errors)

    def is_valid(self, epub_path: Path) -> bool:
        """Return True when validation passes without errors."""
        return self.validate(epub_path).valid
