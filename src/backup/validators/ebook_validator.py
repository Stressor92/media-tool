from __future__ import annotations

import time
import zipfile
from pathlib import Path

from ..models import CheckResult, ValidationResult
from .base_validator import AbstractValidator


class EbookValidator(AbstractValidator):
    def __init__(
        self,
        require_epub_metadata: bool = True,
        require_cover: bool = True,
        require_isbn_if_present: bool = False,
    ) -> None:
        self._require_epub_metadata = require_epub_metadata
        self._require_cover = require_cover
        self._require_isbn_if_present = require_isbn_if_present

    def validate(self, original_path: Path, output_path: Path) -> ValidationResult:
        start = time.perf_counter()
        checks: list[CheckResult] = []

        is_valid_zip = False
        has_title = False
        has_creator = False
        has_cover = False
        has_isbn_in = False
        has_isbn_out = False

        if output_path.exists() and output_path.suffix.lower() == ".epub":
            try:
                with zipfile.ZipFile(output_path, "r") as archive:
                    names = archive.namelist()
                    is_valid_zip = "mimetype" in names
                    opf_candidates = [name for name in names if name.endswith(".opf")]
                    opf_text = ""
                    if opf_candidates:
                        opf_text = archive.read(opf_candidates[0]).decode("utf-8", errors="ignore").lower()
                    has_title = "<dc:title" in opf_text
                    has_creator = "<dc:creator" in opf_text
                    has_cover = ("cover" in opf_text) or any("cover" in name.lower() for name in names)
                    has_isbn_out = "isbn" in opf_text
            except Exception:
                is_valid_zip = False

        if original_path.exists() and original_path.suffix.lower() == ".epub":
            try:
                with zipfile.ZipFile(original_path, "r") as archive:
                    opf_candidates = [name for name in archive.namelist() if name.endswith(".opf")]
                    if opf_candidates:
                        opf_text = archive.read(opf_candidates[0]).decode("utf-8", errors="ignore").lower()
                        has_isbn_in = "isbn" in opf_text
            except Exception:
                has_isbn_in = False

        checks.append(
            CheckResult(name="epub_archive", passed=is_valid_zip, expected="valid epub zip", actual=str(is_valid_zip))
        )
        checks.append(
            CheckResult(
                name="opf_metadata",
                passed=(has_title and has_creator) if self._require_epub_metadata else True,
                expected="title+creator" if self._require_epub_metadata else "disabled",
                actual=f"title={has_title},creator={has_creator}",
            )
        )
        checks.append(
            CheckResult(
                name="cover_present",
                passed=has_cover if self._require_cover else True,
                expected="cover embedded" if self._require_cover else "disabled",
                actual=str(has_cover),
            )
        )
        checks.append(
            CheckResult(
                name="isbn_retained",
                passed=(has_isbn_out if has_isbn_in else True) if self._require_isbn_if_present else True,
                expected="isbn retained" if self._require_isbn_if_present and has_isbn_in else "not required",
                actual=str(has_isbn_out),
            )
        )

        return ValidationResult(
            passed=all(check.passed for check in checks),
            checks=checks,
            duration_ms=(time.perf_counter() - start) * 1000,
        )
