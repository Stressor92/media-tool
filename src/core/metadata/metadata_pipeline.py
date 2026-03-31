from __future__ import annotations

import logging
from pathlib import Path

from core.metadata.artwork_downloader import ArtworkDownloader
from core.metadata.match_selector import MatchSelector, SelectionMode
from core.metadata.models import ArtworkType, MetadataStatus, PipelineResult
from core.metadata.nfo_writer import write_movie_nfo
from core.metadata.title_parser import parse_title
from core.metadata.tmdb_provider import TmdbProvider

logger = logging.getLogger(__name__)


class MetadataPipeline:
    def __init__(
        self,
        provider: TmdbProvider,
        selector: MatchSelector | None = None,
        downloader: ArtworkDownloader | None = None,
        artwork_types: list[ArtworkType] | None = None,
        overwrite: bool = False,
        dry_run: bool = False,
    ) -> None:
        self._provider = provider
        self._selector = selector or MatchSelector(SelectionMode.AUTO)
        self._downloader = downloader or ArtworkDownloader(
            types=artwork_types or [ArtworkType.POSTER, ArtworkType.FANART],
            overwrite=overwrite,
        )
        self._overwrite = overwrite
        self._dry_run = dry_run

    def process_file(self, video_path: Path) -> PipelineResult:
        movie_dir = video_path.parent
        nfo_path = movie_dir / f"{video_path.stem}.nfo"

        if nfo_path.exists() and not self._overwrite:
            return PipelineResult(
                status=MetadataStatus.SKIPPED,
                source_path=video_path,
                movie_dir=movie_dir,
                nfo_path=nfo_path,
                skipped_reason="NFO already exists.",
            )

        parsed = parse_title(video_path)
        logger.info("TMDB search for '%s' (%s)", parsed.title, parsed.year or "unknown")

        search_results = self._provider.search(parsed.title, parsed.year, limit=8)
        if not search_results:
            return PipelineResult(
                status=MetadataStatus.NOT_FOUND,
                source_path=video_path,
                movie_dir=movie_dir,
                error=f"No TMDB match for '{parsed.title}'",
            )

        selection = self._selector.select(search_results, parsed.title, parsed.year)
        if selection.skipped or selection.selected is None:
            return PipelineResult(
                status=MetadataStatus.SKIPPED,
                source_path=video_path,
                movie_dir=movie_dir,
                search_results=search_results,
                skipped_reason="Skipped by selection.",
            )

        if self._dry_run:
            return PipelineResult(
                status=MetadataStatus.SKIPPED,
                source_path=video_path,
                movie_dir=movie_dir,
                search_results=search_results,
                skipped_reason="dry_run",
            )

        try:
            metadata = self._provider.get_movie_metadata(selection.selected.tmdb_id)
            write_movie_nfo(metadata, nfo_path)
            artwork_files = self._downloader.download_all(metadata, movie_dir)
        except Exception as exc:
            return PipelineResult(
                status=MetadataStatus.FAILED,
                source_path=video_path,
                movie_dir=movie_dir,
                error=str(exc),
            )

        return PipelineResult(
            status=MetadataStatus.SUCCESS,
            source_path=video_path,
            movie_dir=movie_dir,
            metadata=metadata,
            nfo_path=nfo_path,
            artwork_files=artwork_files,
            search_results=search_results,
        )

    def process_directory(self, root_dir: Path, recursive: bool = True) -> list[PipelineResult]:
        pattern = "**/*" if recursive else "*"
        files = [
            file
            for file in sorted(root_dir.glob(pattern))
            if file.is_file() and file.suffix.lower() in {".mkv", ".mp4", ".avi"}
        ]
        return [self.process_file(file) for file in files]
