# src/core/translation/converter.py
"""
Public entry point for subtitle format conversions.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path

from core.translation.format_registry import FormatRegistry
from core.translation.models import SubtitleFormat
from core.translation.style_mapper import adapt_styles_for_target

logger = logging.getLogger(__name__)


class ConversionStatus(Enum):
    SUCCESS = auto()
    SKIPPED = auto()
    FAILED = auto()


@dataclass
class ConversionResult:
    status: ConversionStatus
    source_path: Path
    output_path: Path | None = None
    source_format: SubtitleFormat | None = None
    target_format: SubtitleFormat | None = None
    segments_converted: int = 0
    duration_seconds: float = 0.0
    error_message: str | None = None
    warnings: list[str] = field(default_factory=list)


class SubtitleConverter:
    """
    Converts subtitle files between all supported formats.

    Usage:
        converter = SubtitleConverter()
        result = converter.convert(Path("movie.en.srt"), SubtitleFormat.TTML)
        result = converter.convert(Path("broadcast.stl"), SubtitleFormat.SRT)
    """

    def convert(
        self,
        source_path: Path,
        target_format: SubtitleFormat,
        output_path: Path | None = None,
        overwrite: bool = False,
        dry_run: bool = False,
    ) -> ConversionResult:
        start = time.monotonic()

        if not source_path.exists():
            return ConversionResult(
                status=ConversionStatus.FAILED,
                source_path=source_path,
                error_message=f"File not found: {source_path}",
            )

        source_format = FormatRegistry.detect_format(source_path)

        if source_format.is_bitmap:
            return ConversionResult(
                status=ConversionStatus.FAILED,
                source_path=source_path,
                source_format=source_format,
                error_message=(
                    f"{source_format.value.upper()} is a Bitmap format. "
                    f"Use 'media-tool subtitle ocr' for conversion."
                ),
            )

        if source_format == SubtitleFormat.UNKNOWN:
            return ConversionResult(
                status=ConversionStatus.FAILED,
                source_path=source_path,
                error_message="Format could not be detected.",
            )

        if source_format == target_format:
            return ConversionResult(
                status=ConversionStatus.SKIPPED,
                source_path=source_path,
                source_format=source_format,
                target_format=target_format,
                error_message="Source and target format are identical.",
            )

        # Resolve canonical target for SSA/DFXP aliases
        resolved_target = target_format
        if target_format == SubtitleFormat.SSA:
            resolved_target = SubtitleFormat.ASS
        elif target_format == SubtitleFormat.DFXP:
            resolved_target = SubtitleFormat.TTML

        resolved_output = output_path or self._default_output(source_path, resolved_target)

        if resolved_output.exists() and not overwrite:
            return ConversionResult(
                status=ConversionStatus.SKIPPED,
                source_path=source_path,
                output_path=resolved_output,
                source_format=source_format,
                target_format=resolved_target,
                error_message="Output file exists (use --overwrite to replace).",
            )

        if dry_run:
            return ConversionResult(
                status=ConversionStatus.SKIPPED,
                source_path=source_path,
                output_path=resolved_output,
                source_format=source_format,
                target_format=resolved_target,
                error_message="dry_run",
            )

        try:
            reader = FormatRegistry.get_reader(source_format)
            writer = FormatRegistry.get_writer(resolved_target)

            doc = reader(source_path)
            adapted_doc = adapt_styles_for_target(doc, resolved_target)
            writer(adapted_doc, resolved_output)

            elapsed = round(time.monotonic() - start, 2)
            logger.info(
                "%s → %s in %.2fs (%d segments)",
                source_format.value,
                resolved_target.value,
                elapsed,
                len(doc.segments),
            )

            return ConversionResult(
                status=ConversionStatus.SUCCESS,
                source_path=source_path,
                output_path=resolved_output,
                source_format=source_format,
                target_format=resolved_target,
                segments_converted=len(doc.segments),
                duration_seconds=elapsed,
            )

        except Exception as exc:
            logger.exception("Conversion failed: %s", exc)
            return ConversionResult(
                status=ConversionStatus.FAILED,
                source_path=source_path,
                source_format=source_format,
                target_format=resolved_target,
                error_message=str(exc),
            )

    def convert_batch(
        self,
        sources: list[Path],
        target_format: SubtitleFormat,
        output_dir: Path | None = None,
        overwrite: bool = False,
    ) -> list[ConversionResult]:
        results: list[ConversionResult] = []
        for src in sources:
            if output_dir is not None:
                out: Path | None = output_dir / self._default_output(src, target_format).name
            else:
                out = None
            results.append(self.convert(src, target_format, output_path=out, overwrite=overwrite))
        return results

    @staticmethod
    def _default_output(source: Path, target_format: SubtitleFormat) -> Path:
        return source.with_suffix(f".{target_format.value}")
