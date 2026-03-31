"""Orchestrate trailer discovery and downloads for movie libraries."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path
from typing import Callable, Protocol, cast

from core.video.movie_folder_scanner import MovieFolder, MovieFolderScanner
from core.video.trailer_search import SearchRunner, TrailerSearchResult, TrailerSearchService
from utils.jellyfin_naming import JellyfinNaming
from utils.ytdlp_runner import DownloadResult

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[int, int, str], None]


class DownloadRunner(Protocol):
    """Structural interface for trailer download execution."""

    def download(
        self,
        url: str,
        output_path: Path,
        timeout_seconds: int = 600,
    ) -> DownloadResult: ...


class SearchService(Protocol):
    """Structural interface for trailer candidate search."""

    def search_trailer(
        self,
        movie_name: str,
        year: int | None = None,
        preferred_languages: tuple[str, ...] = ("en", "de"),
        max_results_per_language: int = 8,
    ) -> TrailerSearchResult: ...


class FolderScanner(Protocol):
    """Structural interface for movie folder discovery."""

    def scan_library(
        self,
        root_path: Path,
        skip_with_trailer: bool = True,
    ) -> list[MovieFolder]: ...


@dataclass(slots=True)
class TrailerDownloadResult:
    """Final status for one movie folder trailer operation."""

    movie_folder: Path
    movie_name: str
    year: int | None
    success: bool
    trailer_path: Path | None = None
    language: str | None = None
    source_url: str | None = None
    selected_title: str | None = None
    error: str | None = None
    skipped: bool = False
    dry_run: bool = False


class TrailerDownloadService:
    """High-level trailer workflow service for Jellyfin movie libraries."""

    def __init__(
        self,
        ytdlp_runner: DownloadRunner,
        search_service: SearchService | None = None,
        scanner: FolderScanner | None = None,
    ) -> None:
        self.ytdlp_runner = ytdlp_runner
        self.search_service: SearchService
        if search_service is None:
            if not hasattr(ytdlp_runner, "search"):
                raise TypeError("search_service is required when ytdlp_runner has no search method")
            self.search_service = TrailerSearchService(cast(SearchRunner, ytdlp_runner))
        else:
            self.search_service = search_service
        self.scanner = scanner or MovieFolderScanner()

    def process_library(
        self,
        library_path: Path,
        preferred_languages: tuple[str, ...] = ("en", "de"),
        dry_run: bool = False,
        skip_existing: bool = True,
        max_downloads: int = 0,
        progress_callback: ProgressCallback | None = None,
    ) -> list[TrailerDownloadResult]:
        movie_folders = self.scanner.scan_library(
            root_path=library_path,
            skip_with_trailer=skip_existing,
        )
        if max_downloads > 0:
            movie_folders = movie_folders[:max_downloads]

        results: list[TrailerDownloadResult] = []
        total = len(movie_folders)
        for index, movie_folder in enumerate(movie_folders, start=1):
            if progress_callback is not None:
                progress_callback(index - 1, total, movie_folder.movie_name)

            result = self.process_movie(
                movie_folder=movie_folder,
                preferred_languages=preferred_languages,
                dry_run=dry_run,
            )
            results.append(result)

        if progress_callback is not None:
            progress_callback(total, total, "completed")

        return results

    def process_movie(
        self,
        movie_folder: MovieFolder,
        preferred_languages: tuple[str, ...] = ("en", "de"),
        dry_run: bool = False,
    ) -> TrailerDownloadResult:
        search_result = self.search_service.search_trailer(
            movie_name=movie_folder.movie_name,
            year=movie_folder.year,
            preferred_languages=preferred_languages,
        )

        if not search_result.found or search_result.video_info is None:
            return TrailerDownloadResult(
                movie_folder=movie_folder.path,
                movie_name=movie_folder.movie_name,
                year=movie_folder.year,
                success=False,
                error=search_result.error or "No trailer found",
            )

        language_suffix: str | None = None
        if len(preferred_languages) > 1 and search_result.language != preferred_languages[0]:
            language_suffix = search_result.language

        trailer_filename = JellyfinNaming.get_trailer_filename(
            movie_name=movie_folder.movie_name,
            year=movie_folder.year,
            language=language_suffix,
        )
        trailer_path = movie_folder.path / trailer_filename

        if dry_run:
            return TrailerDownloadResult(
                movie_folder=movie_folder.path,
                movie_name=movie_folder.movie_name,
                year=movie_folder.year,
                success=True,
                trailer_path=trailer_path,
                language=search_result.language,
                source_url=search_result.video_info.url,
                selected_title=search_result.video_info.title,
                dry_run=True,
            )

        download_result = self.ytdlp_runner.download(
            url=search_result.video_info.url,
            output_path=trailer_path,
        )
        if not download_result.success:
            return TrailerDownloadResult(
                movie_folder=movie_folder.path,
                movie_name=movie_folder.movie_name,
                year=movie_folder.year,
                success=False,
                language=search_result.language,
                source_url=search_result.video_info.url,
                selected_title=search_result.video_info.title,
                error=download_result.error or "Download failed",
            )

        logger.info(
            "Trailer downloaded",
            extra={
                "movie_name": movie_folder.movie_name,
                "movie_folder": str(movie_folder.path),
                "trailer_path": str(download_result.file_path),
                "language": search_result.language,
            },
        )

        return TrailerDownloadResult(
            movie_folder=movie_folder.path,
            movie_name=movie_folder.movie_name,
            year=movie_folder.year,
            success=True,
            trailer_path=download_result.file_path,
            language=search_result.language,
            source_url=search_result.video_info.url,
            selected_title=search_result.video_info.title,
        )
