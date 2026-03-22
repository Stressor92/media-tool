"""
src/core/video/subtitle_processor.py

Subtitle timing, readability optimization and validation.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of SRT file validation.
    
    Attributes:
        is_valid: Whether the SRT file is valid
        errors: List of validation errors (file not found, invalid format, etc.)
        warnings: List of validation warnings (non-critical issues)
    """
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


@dataclass
class TimingSyncResult:
    """Result of subtitle timing synchronization.
    
    Attributes:
        success: Whether timing sync succeeded
        srt_path: Path to the synchronized SRT file
        scale_factor: Time scale factor applied (duration ratio)
        error_message: Error message if sync failed
    """
    success: bool
    srt_path: Optional[Path] = None
    scale_factor: float = 1.0
    error_message: Optional[str] = None


class SubtitleTimingProcessor:

    SRT_TIMESTAMP_RE = re.compile(r"^(\d{2}):(\d{2}):(\d{2}),(\d{3}) --> (\d{2}):(\d{2}):(\d{2}),(\d{3})$")

    def sync_to_video(self, srt_path: Path, video_duration: float, wav_duration: float) -> TimingSyncResult:
        if not srt_path.exists():
            return TimingSyncResult(success=False, error_message=f"SRT not found: {srt_path}")

        if wav_duration <= 0:
            return TimingSyncResult(success=False, error_message="Invalid wav_duration")

        scale_factor = video_duration / wav_duration
        
        if scale_factor <= 0:
            return TimingSyncResult(success=False, error_message="Invalid scale factor")

        try:
            text = srt_path.read_text(encoding="utf-8")
        except Exception as exc:
            return TimingSyncResult(success=False, error_message=f"Cannot read SRT: {exc}")

        lines = text.splitlines()
        updated_lines = []

        for line in lines:
            m = self.SRT_TIMESTAMP_RE.match(line.strip())
            if m:
                start = self._to_seconds(m.group(1), m.group(2), m.group(3), m.group(4))
                end = self._to_seconds(m.group(5), m.group(6), m.group(7), m.group(8))

                start_s = start * scale_factor
                end_s = end * scale_factor

                formatted = f"{self._from_seconds(start_s)} --> {self._from_seconds(end_s)}"
                updated_lines.append(formatted)
            else:
                updated_lines.append(line)

        srt_path.write_text("\n".join(updated_lines), encoding="utf-8")

        if abs(scale_factor - 1.0) > 0.05:
            logger.warning("Significant timing mismatch: %.4fx", scale_factor)

        return TimingSyncResult(success=True, srt_path=srt_path, scale_factor=scale_factor)

    def optimize_readability(self, srt_path: Path) -> Path:
        if not srt_path.exists():
            raise FileNotFoundError(f"SRT not found: {srt_path}")

        text = srt_path.read_text(encoding="utf-8")
        lines = text.splitlines()

        optimized = []
        blank_count = 0

        for line in lines:
            stripped = line.rstrip()
            if stripped == "":
                blank_count += 1
            else:
                blank_count = 0

            if blank_count <= 2:
                optimized.append(stripped)

        srt_path.write_text("\n".join(optimized) + "\n", encoding="utf-8")
        return srt_path

    def validate_srt(self, srt_path: Path) -> ValidationResult:
        result = ValidationResult(is_valid=True)

        if not srt_path.exists():
            result.is_valid = False
            result.errors.append(f"SRT not found: {srt_path}")
            return result

        try:
            text = srt_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            result.is_valid = False
            result.errors.append("SRT is not valid UTF-8")
            return result

        blocks = re.split(r"\n\s*\n", text.strip())

        last_end = -1.0

        for block in blocks:
            lines = block.strip().splitlines()
            if len(lines) < 3:
                result.is_valid = False
                result.errors.append("SRT block has insufficient lines")
                continue

            # index should be integer
            if not lines[0].isdigit():
                result.is_valid = False
                result.errors.append(f"Invalid index in block: {lines[0]}")

            # timestamp
            if not self.SRT_TIMESTAMP_RE.match(lines[1]):
                result.is_valid = False
                result.errors.append(f"Invalid timestamp format: {lines[1]}")
            else:
                groups = self.SRT_TIMESTAMP_RE.match(lines[1])
                start = self._to_seconds(groups.group(1), groups.group(2), groups.group(3), groups.group(4))
                end = self._to_seconds(groups.group(5), groups.group(6), groups.group(7), groups.group(8))

                if start < last_end:
                    result.is_valid = False
                    result.errors.append("Timestamps are not in ascending order")
                if end < start:
                    result.is_valid = False
                    result.errors.append("End time is before start time")

                last_end = end

        return result

    @staticmethod
    def _to_seconds(h: str, m: str, s: str, ms: str) -> float:
        return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000.0

    @staticmethod
    def _from_seconds(seconds: float) -> str:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds - int(seconds)) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"
