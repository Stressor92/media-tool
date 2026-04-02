from __future__ import annotations

from pathlib import Path
import time
import logging

from core.ebook.models import ConversionProfile, ConversionResult, EbookFormat
from utils.calibre_runner import CalibreConversionError, CalibreRunner
from utils.file_operations import FileOperations

logger = logging.getLogger(__name__)


class FormatConverter:
    """E-book conversion service with validation, backup, and dry-run support."""

    SUPPORTED_INPUTS = {EbookFormat.EPUB, EbookFormat.MOBI, EbookFormat.AZW3, EbookFormat.PDF, EbookFormat.AZW}
    SUPPORTED_OUTPUTS = {EbookFormat.EPUB, EbookFormat.MOBI, EbookFormat.AZW3}

    def __init__(self, calibre_runner: CalibreRunner, dry_run: bool = False) -> None:
        self.calibre = calibre_runner
        self.dry_run = dry_run

    def convert(
        self,
        input_path: Path,
        output_format: EbookFormat,
        profile: ConversionProfile | None = None,
        output_dir: Path | None = None,
        create_backup: bool = True,
        overwrite: bool = False,
        timeout: int = 600,
    ) -> ConversionResult:
        if not input_path.exists() or not input_path.is_file():
            return ConversionResult(success=False, error_message=f"Input file does not exist: {input_path}", dry_run=self.dry_run)

        input_format = EbookFormat.from_extension(input_path.suffix)
        if input_format is None or input_format not in self.SUPPORTED_INPUTS:
            return ConversionResult(success=False, error_message=f"Unsupported input format: {input_path.suffix}", dry_run=self.dry_run)

        if output_format not in self.SUPPORTED_OUTPUTS:
            return ConversionResult(success=False, error_message=f"Unsupported output format: {output_format.value}", dry_run=self.dry_run)

        if input_format == output_format:
            return ConversionResult(success=False, error_message="Input and output format are the same", dry_run=self.dry_run)

        target_dir = output_dir if output_dir is not None else input_path.parent
        output_path = target_dir / f"{input_path.stem}.{output_format.value}"

        if output_path.exists() and not overwrite:
            return ConversionResult(success=False, error_message=f"Output already exists: {output_path}", dry_run=self.dry_run)

        original_size = input_path.stat().st_size / (1024 * 1024)
        backup_path: Path | None = None

        if create_backup:
            backup_path = FileOperations.create_backup(input_path, suffix=".pre-convert.bak", dry_run=self.dry_run)

        args: list[str] = []
        if profile is not None:
            args.extend(profile.to_calibre_args())

        if self.dry_run:
            return ConversionResult(
                success=True,
                output_path=output_path,
                original_size_mb=original_size,
                output_size_mb=0.0,
                duration_seconds=0.0,
                backup_path=backup_path,
                dry_run=True,
            )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        start_time = time.time()

        try:
            self.calibre.convert(input_path, output_path, extra_args=args, timeout=timeout)
        except CalibreConversionError as exc:
            return ConversionResult(
                success=False,
                original_size_mb=original_size,
                duration_seconds=time.time() - start_time,
                error_message=str(exc),
                backup_path=backup_path,
                dry_run=False,
            )

        duration = time.time() - start_time
        output_size = output_path.stat().st_size / (1024 * 1024) if output_path.exists() else 0.0

        logger.info(
            "Ebook conversion completed",
            extra={
                "input": str(input_path),
                "output": str(output_path),
                "duration_seconds": round(duration, 2),
            },
        )

        return ConversionResult(
            success=True,
            output_path=output_path,
            original_size_mb=original_size,
            output_size_mb=output_size,
            duration_seconds=duration,
            backup_path=backup_path,
            dry_run=False,
        )

    def batch_convert(
        self,
        input_paths: list[Path],
        output_format: EbookFormat,
        profile: ConversionProfile | None = None,
        output_dir: Path | None = None,
        create_backup: bool = True,
        overwrite: bool = False,
        timeout: int = 600,
    ) -> list[ConversionResult]:
        results: list[ConversionResult] = []
        for input_path in input_paths:
            results.append(
                self.convert(
                    input_path,
                    output_format,
                    profile=profile,
                    output_dir=output_dir,
                    create_backup=create_backup,
                    overwrite=overwrite,
                    timeout=timeout,
                )
            )
        return results
