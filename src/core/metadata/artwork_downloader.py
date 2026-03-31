from __future__ import annotations

import concurrent.futures
import logging
from pathlib import Path
from typing import Any

import requests

from core.metadata.models import ArtworkFile, ArtworkType, MovieMetadata
from core.metadata.tmdb_client import TmdbClient

logger = logging.getLogger(__name__)

_ARTWORK_SPECS: dict[ArtworkType, dict[str, str]] = {
    ArtworkType.POSTER: {"filename": "poster.jpg", "size": "w500"},
    ArtworkType.FANART: {"filename": "fanart.jpg", "size": "w1280"},
    ArtworkType.BANNER: {"filename": "banner.jpg", "size": "w1000"},
    ArtworkType.THUMB: {"filename": "thumb.jpg", "size": "w780"},
    ArtworkType.LOGO: {"filename": "logo.png", "size": "original"},
    ArtworkType.DISC: {"filename": "disc.png", "size": "original"},
}


class ArtworkDownloader:
    def __init__(
        self,
        preferred_language: str = "de",
        types: list[ArtworkType] | None = None,
        overwrite: bool = False,
        max_workers: int = 4,
        timeout: int = 30,
    ) -> None:
        self._preferred_language = preferred_language
        self._types = types or [ArtworkType.POSTER, ArtworkType.FANART]
        self._overwrite = overwrite
        self._max_workers = max_workers
        self._timeout = timeout

    def download_all(self, metadata: MovieMetadata, output_dir: Path) -> list[ArtworkFile]:
        tasks: list[tuple[ArtworkType, str, Path]] = []

        for artwork_type in self._types:
            url = self._best_url(metadata, artwork_type)
            if not url:
                continue

            output_path = output_dir / _ARTWORK_SPECS[artwork_type]["filename"]
            if output_path.exists() and not self._overwrite:
                continue

            tasks.append((artwork_type, url, output_path))

        if not tasks:
            return []

        results: list[ArtworkFile] = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=self._max_workers) as executor:
            future_map = {
                executor.submit(self._download_one, url, path): (artwork_type, url, path)
                for artwork_type, url, path in tasks
            }

            for future in concurrent.futures.as_completed(future_map):
                artwork_type, url, path = future_map[future]
                try:
                    if future.result():
                        results.append(
                            ArtworkFile(
                                type=artwork_type,
                                url=url,
                                local_path=path,
                            )
                        )
                        logger.info("Artwork downloaded: %s", path.name)
                except Exception as exc:
                    logger.warning("Artwork download failed (%s): %s", artwork_type.value, exc)

        return results

    def _best_url(self, metadata: MovieMetadata, artwork_type: ArtworkType) -> str | None:
        size = _ARTWORK_SPECS.get(artwork_type, {}).get("size", "original")
        options = {
            ArtworkType.POSTER: metadata.available_posters,
            ArtworkType.FANART: metadata.available_backdrops,
            ArtworkType.LOGO: metadata.available_logos,
        }.get(artwork_type, [])

        if not options:
            if artwork_type == ArtworkType.POSTER and metadata.poster_path:
                return TmdbClient.image_url(metadata.poster_path, size)
            if artwork_type == ArtworkType.FANART and metadata.backdrop_path:
                return TmdbClient.image_url(metadata.backdrop_path, size)
            return None

        for language_filter in [self._preferred_language, None, ""]:
            filtered: list[dict[str, Any]] = []
            for option in options:
                if not isinstance(option, dict):
                    continue
                if language_filter is None:
                    filtered.append(option)
                    continue
                option_lang = option.get("iso_639_1") or ""
                if option_lang == language_filter:
                    filtered.append(option)

            if filtered:
                best = max(filtered, key=lambda item: float(item.get("vote_average", 0.0) or 0.0))
                file_path = best.get("file_path")
                if isinstance(file_path, str) and file_path:
                    return TmdbClient.image_url(file_path, size)

        return None

    def _download_one(self, url: str, path: Path) -> bool:
        path.parent.mkdir(parents=True, exist_ok=True)
        response = requests.get(url, timeout=self._timeout, stream=True)
        response.raise_for_status()

        with path.open("wb") as handle:
            for chunk in response.iter_content(8192):
                handle.write(chunk)

        return True
