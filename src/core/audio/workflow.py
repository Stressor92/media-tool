"""
src/core/audio/workflow.py

Complete audio library processing workflow for mixed music collections.
"""

from __future__ import annotations

from collections.abc import Callable
import logging
from pathlib import Path
from typing import Any, TypedDict

from utils.progress import ProgressEvent, emit_progress
from .metadata import AudioMetadataEnhanced, extract_audio_metadata_enhanced
from .enhancement import improve_audio_library
from .organization import organize_music
from .conversion import convert_audio

logger = logging.getLogger(__name__)


class WorkflowStatistics(TypedDict):
    total_files: int
    processed_files: int
    improved_files: int
    organized_files: int
    converted_files: int
    errors: int


class WorkflowResults(TypedDict):
    scanned_files: list[AudioMetadataEnhanced]
    improved_files: list[str]
    organized_files: list[str]
    converted_files: list[str]
    errors: list[str]
    statistics: WorkflowStatistics


class ScanResults(TypedDict):
    files: list[AudioMetadataEnhanced]


class ConversionResults(TypedDict):
    converted: list[str]
    errors: int


def process_audio_library_workflow(
    input_dir: Path,
    output_dir: Path,
    format: str = "flac",
    improve: bool = True,
    scan_only: bool = False,
    overwrite: bool = False,
    progress_callback: Callable[[ProgressEvent], None] | None = None,
) -> WorkflowResults:
    """
    Complete music library processing workflow.

    This function provides a comprehensive solution for mixed music libraries:
    1. Scan and analyze all audio files with metadata extraction
    2. Improve audio quality (remove silence, normalize volume, enhance quality)
    3. Organize files into proper directory structure
    4. Convert to consistent format

    Args:
        input_dir: Input directory containing mixed music library.
        output_dir: Output directory for processed music library.
        format: Target audio format (mp3, flac, m4a, aac, opus, ogg).
        improve: Whether to apply audio improvements.
        scan_only: Only scan and analyze, don't process files.
        overwrite: Whether to overwrite existing files.

    Returns:
        Dictionary with processing results and statistics.
    """
    logger.info(f"Starting audio library workflow: {input_dir} → {output_dir}")

    results: WorkflowResults = {
        "scanned_files": [],
        "improved_files": [],
        "organized_files": [],
        "converted_files": [],
        "errors": [],
        "statistics": {
            "total_files": 0,
            "processed_files": 0,
            "improved_files": 0,
            "organized_files": 0,
            "converted_files": 0,
            "errors": 0,
        }
    }

    # Step 1: Scan and analyze all audio files
    logger.info("Step 1: Scanning audio files...")
    emit_progress(
        progress_callback,
        ProgressEvent("workflow", 0, 0, "", "info", "Step 1/4: scanning audio files"),
    )
    scan_results = _scan_audio_library(input_dir, progress_callback=progress_callback)
    results["scanned_files"] = scan_results["files"]
    results["statistics"]["total_files"] = len(scan_results["files"])

    if scan_only:
        logger.info("Scan-only mode: returning scan results")
        return results

    # Step 2: Improve audio quality (optional)
    if improve:
        logger.info("Step 2: Improving audio quality...")
        emit_progress(
            progress_callback,
            ProgressEvent("workflow", 0, 0, "", "info", "Step 2/4: improving audio files"),
        )
        temp_dir = output_dir / "_temp_improved"
        temp_dir.mkdir(exist_ok=True)

        try:
            improvement_results = improve_audio_library(
                input_dir=input_dir,
                output_dir=temp_dir,
                remove_silence_flag=True,
                normalize_volume=True,
                enhance_quality=True,
                overwrite=overwrite,
                progress_callback=progress_callback,
            )

            results["statistics"]["improved_files"] = improvement_results.get("improved", 0)

            # Use improved files as input for next steps
            processing_input_dir = temp_dir
        except Exception as e:
            logger.error(f"Audio improvement failed: {e}")
            results["errors"].append(f"Improvement failed: {e}")
            results["statistics"]["errors"] += 1
            # Continue with original files
            processing_input_dir = input_dir
    else:
        processing_input_dir = input_dir

    # Step 3: Organize files into proper structure
    logger.info("Step 3: Organizing files...")
    emit_progress(
        progress_callback,
        ProgressEvent("workflow", 0, 0, "", "info", "Step 3/4: organizing library"),
    )
    try:
        organization_results = organize_music(
            input_dir=processing_input_dir,
            output_dir=output_dir,
            convert_format=None,  # We'll handle conversion separately
            overwrite=overwrite,
            progress_callback=progress_callback,
        )

        results["statistics"]["organized_files"] = organization_results.get("processed", 0)
        results["statistics"]["errors"] += organization_results.get("errors", 0)

    except Exception as e:
        logger.error(f"Organization failed: {e}")
        results["errors"].append(f"Organization failed: {e}")
        results["statistics"]["errors"] += 1
        return results

    # Step 4: Convert to consistent format
    logger.info("Step 4: Converting to consistent format...")
    emit_progress(
        progress_callback,
        ProgressEvent("workflow", 0, 0, "", "info", f"Step 4/4: converting organized files to {format}"),
    )
    try:
        conversion_results = _convert_organized_library(
            organized_dir=output_dir,
            target_format=format,
            overwrite=overwrite,
            progress_callback=progress_callback,
        )

        results["converted_files"] = conversion_results["converted"]
        results["statistics"]["converted_files"] = len(conversion_results["converted"])
        results["statistics"]["errors"] += conversion_results["errors"]

    except Exception as e:
        logger.error(f"Conversion failed: {e}")
        results["errors"].append(f"Conversion failed: {e}")
        results["statistics"]["errors"] += 1

    # Cleanup temporary directory
    if improve and temp_dir.exists():
        try:
            import shutil
            shutil.rmtree(temp_dir)
            logger.info("Cleaned up temporary directory")
        except Exception as e:
            logger.warning(f"Failed to cleanup temp directory: {e}")

    results["statistics"]["processed_files"] = (
        results["statistics"]["improved_files"] +
        results["statistics"]["organized_files"] +
        results["statistics"]["converted_files"]
    )

    logger.info("Audio library workflow completed")
    return results


def _scan_audio_library(
    input_dir: Path,
    progress_callback: Callable[[ProgressEvent], None] | None = None,
) -> ScanResults:
    """Scan audio library and extract metadata."""
    files: list[AudioMetadataEnhanced] = []
    audio_extensions = {'.mp3', '.flac', '.m4a', '.aac', '.ogg', '.opus', '.wav', '.wma'}

    matching_files = [
        file_path
        for file_path in input_dir.rglob('*')
        if file_path.is_file() and file_path.suffix.lower() in audio_extensions
    ]
    total = len(matching_files)

    for index, file_path in enumerate(matching_files, start=1):
        emit_progress(
            progress_callback,
            ProgressEvent("scan-audio", index, total, file_path.name, "start", str(file_path)),
        )
        if file_path.is_file() and file_path.suffix.lower() in audio_extensions:
            try:
                metadata = extract_audio_metadata_enhanced(file_path)
                if metadata is not None:
                    files.append(metadata)
                    emit_progress(
                        progress_callback,
                        ProgressEvent("scan-audio", index, total, file_path.name, "success", "Metadata extracted"),
                    )
            except Exception as e:
                logger.warning(f"Failed to extract metadata from {file_path}: {e}")
                emit_progress(
                    progress_callback,
                    ProgressEvent("scan-audio", index, total, file_path.name, "failed", str(e)),
                )

    return {"files": files}


def _convert_organized_library(
    organized_dir: Path,
    target_format: str,
    overwrite: bool = False,
    progress_callback: Callable[[ProgressEvent], None] | None = None,
) -> ConversionResults:
    """Convert organized library to consistent format."""
    converted = []
    errors = 0

    audio_extensions = {'.mp3', '.flac', '.m4a', '.aac', '.ogg', '.opus', '.wav', '.wma'}

    matching_files = [
        file_path
        for file_path in organized_dir.rglob('*')
        if file_path.is_file() and file_path.suffix.lower() in audio_extensions
    ]
    to_convert = [
        file_path for file_path in matching_files if file_path.suffix.lower() != f'.{target_format.lower()}'
    ]
    total = len(to_convert)

    for index, file_path in enumerate(to_convert, start=1):
        if file_path.is_file() and file_path.suffix.lower() in audio_extensions:
            emit_progress(
                progress_callback,
                ProgressEvent("convert-audio", index, total, file_path.name, "start", str(file_path)),
            )

            try:
                output_file = file_path.with_suffix(f'.{target_format}')
                result = convert_audio(
                    input_file=file_path,
                    output_file=output_file,
                    format=target_format,
                    overwrite=overwrite,
                )

                if result.success:
                    converted.append(str(output_file))
                    # Remove original file after successful conversion
                    file_path.unlink()
                    emit_progress(
                        progress_callback,
                        ProgressEvent("convert-audio", index, total, file_path.name, "success", f"Created {output_file.name}"),
                    )
                else:
                    errors += 1
                    emit_progress(
                        progress_callback,
                        ProgressEvent("convert-audio", index, total, file_path.name, "failed", "Conversion failed"),
                    )

            except Exception as e:
                logger.error(f"Failed to convert {file_path}: {e}")
                errors += 1
                emit_progress(
                    progress_callback,
                    ProgressEvent("convert-audio", index, total, file_path.name, "failed", str(e)),
                )

    return {"converted": converted, "errors": errors}