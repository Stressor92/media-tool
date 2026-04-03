from __future__ import annotations

import time
from pathlib import Path

from utils.ffprobe_runner import probe_file

from ..models import CheckResult, ValidationResult
from .base_validator import AbstractValidator


class AudiobookValidator(AbstractValidator):
    def __init__(self, duration_tolerance: float = 0.05, require_chapters: bool = True) -> None:
        self._duration_tolerance = max(0.0, duration_tolerance)
        self._require_chapters = require_chapters

    def validate(self, original_path: Path, output_path: Path) -> ValidationResult:
        start = time.perf_counter()
        checks: list[CheckResult] = []

        orig = probe_file(original_path)
        out = probe_file(output_path)

        if orig.success and out.success:
            orig_duration = float(orig.format.get("duration", 0.0) or 0.0)
            out_duration = float(out.format.get("duration", 0.0) or 0.0)
            delta_ratio = 0.0 if orig_duration <= 0 else abs(out_duration - orig_duration) / orig_duration
            checks.append(
                CheckResult(
                    name="duration_tolerance",
                    passed=delta_ratio <= self._duration_tolerance,
                    expected=f"<= {self._duration_tolerance:.2%}",
                    actual=f"{delta_ratio:.2%}",
                )
            )

            chapters = out.data.get("chapters", [])
            chapter_count = len(chapters) if isinstance(chapters, list) else 0
            checks.append(
                CheckResult(
                    name="chapters_present",
                    passed=(chapter_count >= 1) if self._require_chapters else True,
                    expected=">=1" if self._require_chapters else "disabled",
                    actual=str(chapter_count),
                )
            )

            out_format = str(out.format.get("format_name", ""))
            valid_format = any(fmt in out_format for fmt in ("mp3", "ipod", "m4a", "mov", "mp4"))
            checks.append(CheckResult(name="format_valid", passed=valid_format, expected="m4b/mp3", actual=out_format))
        else:
            checks.append(CheckResult(name="ffprobe_success", passed=False, expected="probe success", actual="failed"))

        checks.append(
            CheckResult(
                name="file_size_nonzero",
                passed=output_path.exists() and output_path.stat().st_size > 0,
                expected="> 0",
                actual=str(output_path.stat().st_size if output_path.exists() else 0),
            )
        )

        return ValidationResult(
            passed=all(check.passed for check in checks),
            checks=checks,
            duration_ms=(time.perf_counter() - start) * 1000,
        )
