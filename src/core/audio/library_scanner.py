"""Library-wide audio scanning orchestration."""

from __future__ import annotations

import logging
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Protocol

from .metadata_extractor import AudioFileMetadata

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[int, int], None]


class MetadataExtractorLike(Protocol):
    def extract(self, file_path: Path) -> AudioFileMetadata: ...


class LibraryScanner:
    """Scan a music library recursively and extract metadata in parallel."""

    SUPPORTED_EXTENSIONS = {
        ".mp3",
        ".flac",
        ".m4a",
        ".aac",
        ".ogg",
        ".opus",
        ".wav",
        ".wma",
        ".ape",
        ".wv",
        ".aiff",
        ".aif",
    }

    def __init__(self, metadata_extractor: MetadataExtractorLike, max_workers: int = 4):
        self.extractor = metadata_extractor
        self.max_workers = max(1, max_workers)

    def scan(
        self,
        library_path: Path,
        progress_callback: ProgressCallback | None = None,
        recursive: bool = True,
    ) -> list[AudioFileMetadata]:
        """Scan an audio library and return metadata for all supported files."""
        audio_files = self.find_audio_files(library_path, recursive=recursive)
        logger.info("Found %d audio file(s) in %s", len(audio_files), library_path)

        if not audio_files:
            return []

        results: list[AudioFileMetadata] = []
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_file = {
                executor.submit(self.extractor.extract, file_path): file_path for file_path in audio_files
            }

            for index, future in enumerate(as_completed(future_to_file), start=1):
                file_path = future_to_file[future]
                try:
                    results.append(future.result())
                except Exception as exc:
                    logger.error("Failed to process %s: %s", file_path, exc)
                    results.append(
                        AudioFileMetadata(
                            file_path=file_path.resolve(),
                            file_name=file_path.name,
                            file_size_mb=0.0,
                            directory=str(file_path.parent.resolve()),
                            extension=file_path.suffix.lower().lstrip("."),
                            duration_seconds=0.0,
                            error_message=str(exc),
                        )
                    )

                if progress_callback is not None:
                    progress_callback(index, len(audio_files))

        return sorted(results, key=lambda item: str(item.file_path).lower())

    def find_audio_files(self, root_path: Path, recursive: bool = True) -> list[Path]:
        """Return a sorted list of supported audio files beneath a root path."""
        if not root_path.is_dir():
            return []

        iterator = root_path.rglob("*") if recursive else root_path.glob("*")
        files = [path for path in iterator if path.is_file() and path.suffix.lower() in self.SUPPORTED_EXTENSIONS]
        return sorted(files, key=lambda path: str(path).lower())
