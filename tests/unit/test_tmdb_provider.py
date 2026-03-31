from unittest.mock import MagicMock

from core.metadata.tmdb_provider import TmdbProvider


def test_search_filters_invalid_and_respects_limit() -> None:
    client = MagicMock()
    client.get.return_value = {
        "results": [
            {"id": 1, "title": "A", "release_date": "2010-07-16", "genre_ids": [10, "x"]},
            {"id": 2, "title": "B", "release_date": "invalid"},
            {"title": "missing id"},
            {"id": 3, "title": "C"},
        ]
    }
    provider = TmdbProvider(client)

    results = provider.search("any", limit=2)

    assert len(results) == 2
    assert results[0].tmdb_id == 1
    assert results[0].year == 2010
    assert results[0].genre_ids == [10]
    assert results[1].tmdb_id == 2
    assert results[1].year is None


def test_search_returns_empty_for_non_list_payload() -> None:
    client = MagicMock()
    client.get.return_value = {"results": {"not": "a list"}}

    provider = TmdbProvider(client)

    assert provider.search("x") == []


def test_get_movie_metadata_normalizes_nested_fields() -> None:
    client = MagicMock()
    client.get_with_fallback.return_value = {
        "imdb_id": "tt123",
        "title": "Movie",
        "original_title": "Original Movie",
        "release_date": "2024-01-10",
        "overview": "Summary",
        "tagline": "Tag",
        "runtime": "120",
        "vote_average": 7.5,
        "vote_count": 200,
        "popularity": 15.2,
        "genres": [{"name": "Action"}, {"name": ""}],
        "production_companies": [{"name": "Studio A"}],
        "production_countries": [{"name": "Germany"}],
        "keywords": {"keywords": [{"name": "hero"}, {"name": ""}]},
        "release_dates": {
            "results": [
                {
                    "iso_3166_1": "DE",
                    "release_dates": [{"certification": "FSK 12"}],
                }
            ]
        },
        "credits": {
            "cast": [
                {"name": "Actor 2", "character": "B", "order": 2, "id": 12},
                {"name": "Actor 1", "character": "A", "order": 1, "id": 11},
            ],
            "crew": [
                {"name": "Dir", "job": "Director", "department": "Directing"},
                {"name": "Ignored", "job": "Grip", "department": "Crew"},
            ],
        },
        "videos": {
            "results": [
                {"type": "Trailer", "site": "YouTube", "key": "abc123"},
            ]
        },
        "belongs_to_collection": {"name": "Collection 1"},
        "poster_path": "/poster.jpg",
        "backdrop_path": "/backdrop.jpg",
        "images": {
            "posters": [{"file_path": "/p.jpg"}],
            "backdrops": [{"file_path": "/b.jpg"}],
            "logos": [{"file_path": "/l.png"}],
        },
    }
    provider = TmdbProvider(client)

    metadata = provider.get_movie_metadata(42)

    assert metadata.tmdb_id == 42
    assert metadata.year == 2024
    assert metadata.runtime == 120
    assert metadata.mpaa_rating == "FSK 12"
    assert metadata.genres == ["Action"]
    assert metadata.keywords == ["hero"]
    assert [actor.name for actor in metadata.cast] == ["Actor 1", "Actor 2"]
    assert [crew.job for crew in metadata.crew] == ["Director"]
    assert metadata.trailer_url == "https://www.youtube.com/watch?v=abc123"
    assert metadata.collections == ["Collection 1"]
    assert len(metadata.available_posters) == 1
