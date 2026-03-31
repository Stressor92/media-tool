from pathlib import Path
from unittest.mock import MagicMock

import pytest

from core.metadata.metadata_pipeline import MetadataPipeline
from core.metadata.models import MetadataStatus, MovieMetadata, TmdbSearchResult


def _search_result() -> TmdbSearchResult:
    return TmdbSearchResult(
        tmdb_id=27205,
        title="Inception",
        original_title="Inception",
        year=2010,
        overview="...",
        popularity=80.0,
        vote_average=8.8,
        vote_count=1_000_000,
        poster_path="/p.jpg",
        backdrop_path="/b.jpg",
    )


def _metadata() -> MovieMetadata:
    return MovieMetadata(
        tmdb_id=27205,
        imdb_id="tt1375666",
        title="Inception",
        original_title="Inception",
        sort_title="Inception",
        year=2010,
        release_date="2010-07-16",
        overview="...",
        tagline="...",
        runtime=148,
        vote_average=8.8,
        vote_count=1_000_000,
        popularity=45.0,
        mpaa_rating="FSK 12",
        genres=["Action"],
        studios=[],
        countries=[],
        keywords=[],
        cast=[],
        crew=[],
        collections=[],
        trailer_url=None,
        poster_path="/p.jpg",
        backdrop_path="/b.jpg",
        available_posters=[],
        available_backdrops=[],
        available_logos=[],
    )


@pytest.fixture()
def provider() -> MagicMock:
    mock_provider = MagicMock()
    mock_provider.search.return_value = [_search_result()]
    mock_provider.get_movie_metadata.return_value = _metadata()
    return mock_provider


@pytest.fixture()
def downloader() -> MagicMock:
    mock_downloader = MagicMock()
    mock_downloader.download_all.return_value = []
    return mock_downloader


def test_success_creates_nfo(provider: MagicMock, downloader: MagicMock, tmp_path: Path) -> None:
    file_path = tmp_path / "Inception (2010)" / "Inception (2010).mkv"
    file_path.parent.mkdir(parents=True)
    file_path.touch()

    result = MetadataPipeline(provider=provider, downloader=downloader).process_file(file_path)

    assert result.status == MetadataStatus.SUCCESS
    assert result.nfo_path is not None
    assert result.nfo_path.exists()


def test_skips_existing_nfo(provider: MagicMock, downloader: MagicMock, tmp_path: Path) -> None:
    file_path = tmp_path / "Inception (2010)" / "Inception (2010).mkv"
    nfo_path = tmp_path / "Inception (2010)" / "Inception (2010).nfo"
    file_path.parent.mkdir(parents=True)
    file_path.touch()
    nfo_path.write_text("<movie/>", encoding="utf-8")

    result = MetadataPipeline(
        provider=provider,
        downloader=downloader,
        overwrite=False,
    ).process_file(file_path)

    assert result.status == MetadataStatus.SKIPPED
    provider.search.assert_not_called()


def test_not_found(provider: MagicMock, downloader: MagicMock, tmp_path: Path) -> None:
    provider.search.return_value = []
    file_path = tmp_path / "Ghost Film XYZ" / "Ghost Film XYZ.mkv"
    file_path.parent.mkdir(parents=True)
    file_path.touch()

    result = MetadataPipeline(provider=provider, downloader=downloader).process_file(file_path)

    assert result.status == MetadataStatus.NOT_FOUND


def test_dry_run_no_nfo(provider: MagicMock, downloader: MagicMock, tmp_path: Path) -> None:
    file_path = tmp_path / "Inception (2010)" / "Inception (2010).mkv"
    file_path.parent.mkdir(parents=True)
    file_path.touch()

    MetadataPipeline(provider=provider, downloader=downloader, dry_run=True).process_file(file_path)
    nfo_path = tmp_path / "Inception (2010)" / "Inception (2010).nfo"

    assert not nfo_path.exists()
