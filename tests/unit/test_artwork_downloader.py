from pathlib import Path

import pytest

from core.metadata.artwork_downloader import ArtworkDownloader
from core.metadata.models import ArtworkType, MovieMetadata


def _metadata() -> MovieMetadata:
    return MovieMetadata(
        tmdb_id=1,
        imdb_id=None,
        title="Movie",
        original_title="Movie",
        sort_title="Movie",
        year=2024,
        release_date="2024-01-01",
        overview="",
        tagline="",
        runtime=100,
        vote_average=0.0,
        vote_count=0,
        popularity=0.0,
        mpaa_rating=None,
        poster_path=None,
        backdrop_path=None,
        available_posters=[],
        available_backdrops=[],
        available_logos=[],
    )


def test_best_url_prefers_language_then_vote() -> None:
    metadata = _metadata()
    metadata.available_posters = [
        {"iso_639_1": "en", "vote_average": 9.0, "file_path": "/en-high.jpg"},
        {"iso_639_1": "de", "vote_average": 7.0, "file_path": "/de-low.jpg"},
        {"iso_639_1": "de", "vote_average": 8.0, "file_path": "/de-high.jpg"},
    ]
    downloader = ArtworkDownloader(preferred_language="de", types=[ArtworkType.POSTER])

    url = downloader._best_url(metadata, ArtworkType.POSTER)

    assert url is not None
    assert url.endswith("/w500/de-high.jpg")


def test_best_url_falls_back_to_primary_paths() -> None:
    metadata = _metadata()
    metadata.poster_path = "/poster.jpg"
    metadata.backdrop_path = "/backdrop.jpg"
    downloader = ArtworkDownloader(types=[ArtworkType.POSTER, ArtworkType.FANART])

    poster = downloader._best_url(metadata, ArtworkType.POSTER)
    fanart = downloader._best_url(metadata, ArtworkType.FANART)

    assert poster is not None and poster.endswith("/w500/poster.jpg")
    assert fanart is not None and fanart.endswith("/w1280/backdrop.jpg")


def test_download_all_skips_existing_when_no_overwrite(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    metadata = _metadata()
    metadata.poster_path = "/poster.jpg"
    output_dir = tmp_path / "movie"
    output_dir.mkdir()
    (output_dir / "poster.jpg").write_bytes(b"existing")

    downloader = ArtworkDownloader(types=[ArtworkType.POSTER], overwrite=False)
    calls: list[tuple[str, Path]] = []

    def _fake_download(url: str, path: Path) -> bool:
        calls.append((url, path))
        return True

    monkeypatch.setattr(downloader, "_download_one", _fake_download)

    results = downloader.download_all(metadata, output_dir)

    assert results == []
    assert calls == []


def test_download_all_collects_only_successes(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    metadata = _metadata()
    metadata.poster_path = "/poster.jpg"
    metadata.backdrop_path = "/backdrop.jpg"

    downloader = ArtworkDownloader(types=[ArtworkType.POSTER, ArtworkType.FANART], overwrite=True)

    def _fake_download(url: str, path: Path) -> bool:
        return path.name == "poster.jpg"

    monkeypatch.setattr(downloader, "_download_one", _fake_download)

    results = downloader.download_all(metadata, tmp_path)

    assert len(results) == 1
    assert results[0].type == ArtworkType.POSTER
    assert results[0].local_path.name == "poster.jpg"
