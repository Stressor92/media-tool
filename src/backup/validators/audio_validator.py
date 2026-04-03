from __future__ import annotations

import time
from pathlib import Path

from utils.ffprobe_runner import probe_file

from ..models import CheckResult, ValidationResult
from .base_validator import AbstractValidator


class AudioValidator(AbstractValidator):
    def __init__(self, duration_tolerance: float = 0.03, min_audio_bitrate_kbps: int = 0) -> None:
        self._duration_tolerance = max(0.0, duration_tolerance)
        self._min_audio_bitrate_kbps = max(0, min_audio_bitrate_kbps)

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

            out_format = str(out.format.get("format_name", ""))
            checks.append(
                CheckResult(
                    name="format_present",
                    passed=bool(out_format),
                    expected="non-empty format",
                    actual=out_format or "",
                )
            )

            out_audio = out.audio_streams()
            bitrate_kbps = 0
            if out_audio:
                bitrate_kbps = int((float(out_audio[0].get("bit_rate", 0) or 0.0)) / 1000)
            checks.append(
                CheckResult(
                    name="min_audio_bitrate",
                    passed=(bitrate_kbps >= self._min_audio_bitrate_kbps) if self._min_audio_bitrate_kbps > 0 else True,
                    expected=(
                        f">= {self._min_audio_bitrate_kbps} kbps" if self._min_audio_bitrate_kbps > 0 else "disabled"
                    ),
                    actual=f"{bitrate_kbps} kbps",
                )
            )
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
