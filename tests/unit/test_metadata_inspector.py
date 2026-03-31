# tests/unit/test_metadata_inspector.py
from unittest.mock import MagicMock

import pytest

from core.jellyfin.library_manager import LibraryManager
from core.jellyfin.metadata_inspector import MetadataInspector
from core.jellyfin.models import ItemType, JellyfinItem, MetadataIssueKind


def _movie(**kwargs) -> JellyfinItem:
    defaults: dict = {
        "id": "m1",
        "name": "Test Movie",
        "item_type": ItemType.MOVIE,
        "path": "/media/movies/Test Movie (2020)/Test Movie (2020).mkv",
        "year": 2020,
        "overview": "A film.",
        "provider_ids": {"Tmdb": "123"},
        "has_image_poster": True,
        "has_image_backdrop": True,
        "raw": {},
    }
    return JellyfinItem(**{**defaults, **kwargs})


def _episode(**kwargs) -> JellyfinItem:
    defaults: dict = {
        "id": "e1",
        "name": "Episode 1",
        "item_type": ItemType.EPISODE,
        "path": "/media/tv/My Show/Season 01/My.Show.S01E01.mkv",
        "series_id": "s1",
        "index_number": 1,
        "parent_index_number": 1,
        "provider_ids": {},
        "raw": {},
        "has_image_poster": False,
        "has_image_backdrop": False,
    }
    return JellyfinItem(**{**defaults, **kwargs})


@pytest.fixture()
def inspector() -> MetadataInspector:
    mock_manager = MagicMock(spec=LibraryManager)
    return MetadataInspector(mock_manager)


class TestMovieChecks:
    def test_complete_movie_has_no_issues(self, inspector: MetadataInspector) -> None:
        issues = inspector._check_movie(_movie())
        assert issues == []

    def test_missing_overview_detected(self, inspector: MetadataInspector) -> None:
        issues = inspector._check_movie(_movie(overview=None))
        kinds = [i.kind for i in issues]
        assert MetadataIssueKind.MISSING_OVERVIEW in kinds

    def test_missing_year_detected(self, inspector: MetadataInspector) -> None:
        issues = inspector._check_movie(_movie(year=None, path="/media/NoYear.mkv"))
        kinds = [i.kind for i in issues]
        assert MetadataIssueKind.MISSING_YEAR in kinds

    def test_missing_year_auto_fixable_when_year_in_path(
        self, inspector: MetadataInspector
    ) -> None:
        issues = inspector._check_movie(_movie(year=None))
        year_issues = [i for i in issues if i.kind == MetadataIssueKind.MISSING_YEAR]
        assert year_issues[0].auto_fixable is True

    def test_missing_poster_detected(self, inspector: MetadataInspector) -> None:
        issues = inspector._check_movie(_movie(has_image_poster=False))
        assert any(i.kind == MetadataIssueKind.MISSING_POSTER for i in issues)

    def test_missing_backdrop_detected(self, inspector: MetadataInspector) -> None:
        issues = inspector._check_movie(_movie(has_image_backdrop=False))
        assert any(i.kind == MetadataIssueKind.MISSING_BACKDROP for i in issues)

    def test_unmatched_when_no_provider_ids(self, inspector: MetadataInspector) -> None:
        issues = inspector._check_movie(_movie(provider_ids={}))
        assert any(i.kind == MetadataIssueKind.UNMATCHED for i in issues)

    def test_unmatched_is_not_auto_fixable(self, inspector: MetadataInspector) -> None:
        issues = inspector._check_movie(_movie(provider_ids={}))
        unmatched = [i for i in issues if i.kind == MetadataIssueKind.UNMATCHED]
        assert unmatched[0].auto_fixable is False


class TestSeriesChecks:
    def test_complete_series_no_issues(self, inspector: MetadataInspector) -> None:
        series = JellyfinItem(
            id="s1",
            name="My Show",
            item_type=ItemType.SERIES,
            overview="A great show.",
            has_image_poster=True,
            has_image_backdrop=False,
            provider_ids={"Tmdb": "1"},
            raw={},
        )
        issues = inspector._check_series(series)
        assert issues == []

    def test_missing_overview_in_series(self, inspector: MetadataInspector) -> None:
        series = JellyfinItem(
            id="s1",
            name="My Show",
            item_type=ItemType.SERIES,
            overview=None,
            has_image_poster=True,
            has_image_backdrop=False,
            provider_ids={},
            raw={},
        )
        issues = inspector._check_series(series)
        assert any(i.kind == MetadataIssueKind.MISSING_OVERVIEW for i in issues)


class TestEpisodeChecks:
    def test_episode_with_all_data_no_issues(
        self, inspector: MetadataInspector
    ) -> None:
        series = JellyfinItem(
            id="s1",
            name="My Show",
            item_type=ItemType.SERIES,
            has_image_poster=True,
            has_image_backdrop=False,
            provider_ids={},
            raw={},
        )
        issues = inspector._check_episode(_episode(), [series])
        assert issues == []

    def test_missing_episode_number_detected(
        self, inspector: MetadataInspector
    ) -> None:
        ep = _episode(index_number=None)
        issues = inspector._check_episode(ep, [])
        assert any(i.kind == MetadataIssueKind.MISSING_EPISODE_NUM for i in issues)

    def test_missing_episode_number_auto_fixable_from_path(
        self, inspector: MetadataInspector
    ) -> None:
        ep = _episode(index_number=None)
        issues = inspector._check_episode(ep, [])
        ep_issues = [
            i for i in issues if i.kind == MetadataIssueKind.MISSING_EPISODE_NUM
        ]
        assert ep_issues[0].auto_fixable is True
        assert ep_issues[0].suggested_fix == "S01E01"

    def test_wrong_series_detected(self, inspector: MetadataInspector) -> None:
        series_a = JellyfinItem(
            id="s1",
            name="Breaking Bad",
            item_type=ItemType.SERIES,
            has_image_poster=True,
            has_image_backdrop=True,
            provider_ids={},
            raw={},
        )
        ep = _episode(
            path="/media/tv/Better Call Saul/Season 01/BCS.S01E01.mkv",
            series_id="s1",
        )
        issues = inspector._check_episode(ep, [series_a])
        assert any(i.kind == MetadataIssueKind.WRONG_SERIES_MATCH for i in issues)

    def test_wrong_series_not_auto_fixable(
        self, inspector: MetadataInspector
    ) -> None:
        series_a = JellyfinItem(
            id="s1",
            name="Breaking Bad",
            item_type=ItemType.SERIES,
            has_image_poster=False,
            has_image_backdrop=False,
            provider_ids={},
            raw={},
        )
        ep = _episode(
            path="/media/tv/Better Call Saul/Season 01/BCS.S01E01.mkv",
            series_id="s1",
        )
        issues = inspector._check_episode(ep, [series_a])
        wrong = [i for i in issues if i.kind == MetadataIssueKind.WRONG_SERIES_MATCH]
        assert wrong[0].auto_fixable is False


class TestDuplicateDetection:
    def test_duplicate_items_flagged(self, inspector: MetadataInspector) -> None:
        items = [
            _movie(id="m1", name="Inception", year=2010),
            _movie(id="m2", name="Inception", year=2010),
        ]
        issues = inspector._check_duplicates(items)
        assert len(issues) == 2
        assert all(i.kind == MetadataIssueKind.DUPLICATE_ITEM for i in issues)

    def test_unique_items_not_flagged(self, inspector: MetadataInspector) -> None:
        items = [
            _movie(id="m1", name="Inception", year=2010),
            _movie(id="m2", name="The Matrix", year=1999),
        ]
        issues = inspector._check_duplicates(items)
        assert issues == []


class TestPathHelpers:
    def test_extract_year_from_path(self, inspector: MetadataInspector) -> None:
        result = inspector._extract_year_from_path(
            "/media/Inception (2010)/Inception.mkv"
        )
        assert result is not None
        assert "2010" in result

    def test_extract_year_returns_none_if_absent(
        self, inspector: MetadataInspector
    ) -> None:
        assert inspector._extract_year_from_path("/media/NoYear.mkv") is None
        assert inspector._extract_year_from_path(None) is None

    def test_extract_episode_from_path(self, inspector: MetadataInspector) -> None:
        assert inspector._extract_episode_from_path("My.Show.S02E05.mkv") == "S02E05"

    def test_extract_episode_case_insensitive(
        self, inspector: MetadataInspector
    ) -> None:
        assert inspector._extract_episode_from_path("show.s01e03.mkv") == "S01E03"

    def test_extract_episode_returns_none_if_absent(
        self, inspector: MetadataInspector
    ) -> None:
        assert inspector._extract_episode_from_path("movie.mkv") is None

    def test_extract_series_from_path(self, inspector: MetadataInspector) -> None:
        result = inspector._extract_series_from_path(
            "/media/tv/My Show/Season 01/ep.mkv"
        )
        assert result == "My Show"

    def test_extract_series_skips_season_folder(
        self, inspector: MetadataInspector
    ) -> None:
        # When parts[-3] (the candidate) starts with "season", return None.
        # Represents a weird layout: .../Season 02/<subfolder>/ep.mkv
        result = inspector._extract_series_from_path(
            "/media/Season 02/extras/ep.mkv"
        )
        # parts[-3] = "Season 02" → starts with "season" → None
        assert result is None

    def test_extract_series_returns_none_for_short_path(
        self, inspector: MetadataInspector
    ) -> None:
        assert inspector._extract_series_from_path("ep.mkv") is None
        assert inspector._extract_series_from_path(None) is None
