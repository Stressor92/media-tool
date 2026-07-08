"""Discover Jellyfin movie folders and detect existing trailers."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path

from utils.jellyfin_naming import JellyfinNaming

logger = logging.getLogger(__name__)

VIDEO_EXTENSIONS = {".mkv", ".mp4", ".avi", ".mov", ".wmv", ".m4v", ".webm"}
_TRAILER_SUFFIX_PATTERN = re.compile(r"\s*-\s*\[?trailer\]?($|-[a-z]{2,3}$)", re.IGNORECASE)


@dataclass(slots=True)
class MovieFolder:
    """Movie folder metadata for trailer processing."""

    path: Path
    movie_name: str
    year: int | None
    has_trailer: bool


class MovieFolderScanner:
    """Scan library folders and return movie candidates."""

    def scan_library(
        self,
        root_path: Path,
        skip_with_trailer: bool = True,
    ) -> list[MovieFolder]:
        if not root_path.exists() or not root_path.is_dir():
            raise ValueError(f"Library root is not a directory: {root_path}")

        movie_folders: list[MovieFolder] = []
        for directory in [root_path, *[path for path in root_path.rglob("*") if path.is_dir()]]:
            if not self._contains_primary_movie_file(directory):
                continue

            movie_name, year = JellyfinNaming.parse_movie_folder_name(directory.name)
            existing_trailer = self._find_existing_trailer(directory)
            has_trailer = existing_trailer is not None

            if skip_with_trailer and has_trailer:
                logger.warning(
                    "Skipping folder because trailer already exists",
                    extra={
                        "context": {
                            "folder": str(directory),
                            "movie_name": movie_name,
                            "existing_trailer": existing_trailer.name if existing_trailer is not None else "-",
                        }
                    },
                )
                continue

            movie_folders.append(
                MovieFolder(
                    path=directory,
                    movie_name=movie_name,
                    year=year,
                    has_trailer=has_trailer,
                )
            )

        logger.info(
            "Movie folder scan complete",
            extra={"root_path": str(root_path), "candidates": len(movie_folders)},
        )
        return sorted(movie_folders, key=lambda folder: str(folder.path).lower())

    @staticmethod
    def _has_existing_trailer(folder_path: Path) -> bool:
        return MovieFolderScanner._find_existing_trailer(folder_path) is not None

    @staticmethod
    def _find_existing_trailer(folder_path: Path) -> Path | None:
        for file in folder_path.iterdir():
            if not file.is_file():
                continue
            if file.suffix.lower() != ".mp4":
                continue
            if _TRAILER_SUFFIX_PATTERN.search(file.stem.lower()) is not None:
                return file
        return None

    @staticmethod
    def _contains_primary_movie_file(folder_path: Path) -> bool:
        for file in folder_path.iterdir():
            if not file.is_file():
                continue
            if file.suffix.lower() not in VIDEO_EXTENSIONS:
                continue
            if _TRAILER_SUFFIX_PATTERN.search(file.stem.lower()) is not None:
                continue
            return True
        return False
