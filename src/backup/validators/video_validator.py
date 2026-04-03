from __future__ import annotations

import time
from pathlib import Path

from utils.ffprobe_runner import probe_file

from ..models import CheckResult, ValidationResult
from .base_validator import AbstractValidator


class VideoValidator(AbstractValidator):
    def __init__(self, duration_tolerance: float = 0.05, require_audio_tracks: bool = True) -> None:
        self._duration_tolerance = max(0.0, duration_tolerance)
        self._require_audio_tracks = require_audio_tracks

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

            out_audio_tracks = len(out.audio_streams())
            checks.append(
                CheckResult(
                    name="audio_tracks_present",
                    passed=(out_audio_tracks >= 1) if self._require_audio_tracks else True,
                    expected=">=1" if self._require_audio_tracks else "disabled",
                    actual=str(out_audio_tracks),
                )
            )

            out_sub_count = len(out.subtitle_streams())
            in_sub_count = len(orig.subtitle_streams())
            checks.append(
                CheckResult(
                    name="subtitles_if_present",
                    passed=(out_sub_count >= 1) if in_sub_count > 0 else True,
                    expected=">=1" if in_sub_count > 0 else "not required",
                    actual=str(out_sub_count),
                )
            )
        else:
            checks.append(
                CheckResult(
                    name="ffprobe_success",
                    passed=False,
                    expected="probe success",
                    actual="failed",
                )
            )

        size_ok = output_path.exists() and output_path.stat().st_size > 0
        checks.append(
            CheckResult(
                name="file_size_nonzero",
                passed=size_ok,
                expected="> 0",
                actual=str(output_path.stat().st_size if output_path.exists() else 0),
            )
        )

        passed = all(check.passed for check in checks)
        return ValidationResult(passed=passed, checks=checks, duration_ms=(time.perf_counter() - start) * 1000)
