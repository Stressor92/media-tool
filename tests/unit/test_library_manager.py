# tests/unit/test_library_manager.py
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from core.jellyfin.client import JellyfinClient
from core.jellyfin.library_manager import LibraryManager
from core.jellyfin.models import ItemType, ScanState


@pytest.fixture()
def mock_client() -> MagicMock:
    return MagicMock(spec=JellyfinClient)


@pytest.fixture()
def manager(mock_client: MagicMock) -> LibraryManager:
    return LibraryManager(mock_client)


class TestRefresh:
    def test_refresh_all_triggers_post(self, manager: LibraryManager, mock_client: MagicMock) -> None:
        result = manager.refresh_all()
        mock_client.post.assert_called_once_with("/Library/Refresh")
        assert result.triggered is True

    def test_refresh_all_returns_failed_on_exception(self, manager: LibraryManager, mock_client: MagicMock) -> None:
        mock_client.post.side_effect = RuntimeError("Server down")
        result = manager.refresh_all()
        assert result.triggered is False
        assert result.error is not None

    def test_refresh_library_calls_correct_endpoint(self, manager: LibraryManager, mock_client: MagicMock) -> None:
        result = manager.refresh_library("lib-42")
        mock_client.post.assert_called_once()
        call_path = mock_client.post.call_args[0][0]
        assert "lib-42" in call_path
        assert result.triggered is True
        assert result.item_id == "lib-42"

    def test_refresh_item_uses_replace_params_when_requested(
        self, manager: LibraryManager, mock_client: MagicMock
    ) -> None:
        manager.refresh_item("item-1", replace_metadata=True)
        params = mock_client.post.call_args[1]["params"]
        assert params["ReplaceAllMetadata"] is True
        assert params["MetadataRefreshMode"] == "FullRefresh"

    def test_refresh_item_default_params_no_replace(self, manager: LibraryManager, mock_client: MagicMock) -> None:
        manager.refresh_item("item-1")
        params = mock_client.post.call_args[1]["params"]
        assert params["ReplaceAllMetadata"] is False


class TestScanStatus:
    def test_scan_status_running(self, manager: LibraryManager, mock_client: MagicMock) -> None:
        mock_client.get.return_value = [
            {
                "Name": "Scan media library",
                "State": "Running",
                "CurrentProgressPercentage": 42.5,
            }
        ]
        status = manager.get_scan_status()
        assert status.state == ScanState.RUNNING
        assert status.progress == pytest.approx(42.5)

    def test_scan_status_idle_when_no_matching_task(self, manager: LibraryManager, mock_client: MagicMock) -> None:
        mock_client.get.return_value = [{"Name": "SomeOtherTask", "State": "Idle"}]
        status = manager.get_scan_status()
        assert status.state == ScanState.IDLE

    def test_scan_status_failed_on_exception(self, manager: LibraryManager, mock_client: MagicMock) -> None:
        mock_client.get.side_effect = RuntimeError("timeout")
        status = manager.get_scan_status()
        assert status.state == ScanState.FAILED

    def test_wait_for_scan_returns_immediately_when_idle(self, manager: LibraryManager) -> None:
        with patch.object(
            manager,
            "get_scan_status",
            return_value=MagicMock(state=ScanState.IDLE),
        ):
            status = manager.wait_for_scan(timeout_seconds=10, poll_interval=0)
        assert status.state == ScanState.IDLE


class TestParseItem:
    def test_parse_item_with_poster(self, manager: LibraryManager) -> None:
        raw = {
            "Id": "abc",
            "Name": "Inception",
            "Type": "Movie",
            "ImageTags": {"Primary": "hash123"},
            "BackdropImageTags": [],
            "ProviderIds": {"Tmdb": "27205"},
        }
        item = manager._parse_item(raw)
        assert item.has_image_poster is True
        assert item.has_image_backdrop is False
        assert item.provider_ids["Tmdb"] == "27205"

    def test_parse_item_unknown_type(self, manager: LibraryManager) -> None:
        raw = {"Id": "x", "Name": "Test", "Type": "Trailer"}
        item = manager._parse_item(raw)
        assert item.item_type == ItemType.UNKNOWN

    def test_parse_item_episode(self, manager: LibraryManager) -> None:
        raw = {
            "Id": "ep1",
            "Name": "Pilot",
            "Type": "Episode",
            "IndexNumber": 1,
            "ParentIndexNumber": 1,
            "SeriesId": "s1",
        }
        item = manager._parse_item(raw)
        assert item.item_type == ItemType.EPISODE
        assert item.index_number == 1
        assert item.series_id == "s1"


class TestFindLibraryForPath:
    def test_find_library_matches_correct_library(self, manager: LibraryManager, mock_client: MagicMock) -> None:
        mock_client.get.return_value = [
            {
                "ItemId": "lib1",
                "Name": "Movies",
                "Locations": ["/media/movies"],
                "CollectionType": "movies",
                "ItemCount": 100,
            }
        ]
        result = manager._find_library_for_path(Path("/media/movies/Inception (2010)"))
        assert result is not None
        assert result.name == "Movies"

    def test_find_library_returns_none_when_no_match(self, manager: LibraryManager, mock_client: MagicMock) -> None:
        mock_client.get.return_value = [
            {
                "ItemId": "lib1",
                "Name": "Movies",
                "Locations": ["/media/movies"],
                "CollectionType": "movies",
                "ItemCount": 0,
            }
        ]
        result = manager._find_library_for_path(Path("/media/music/song.mp3"))
        assert result is None

    def test_refresh_path_falls_back_to_refresh_all(self, manager: LibraryManager, mock_client: MagicMock) -> None:
        mock_client.get.return_value = []
        with patch.object(manager, "refresh_all") as mock_all:
            mock_all.return_value = MagicMock(triggered=True)
            manager.refresh_path(Path("/some/unknown/path"))
            mock_all.assert_called_once()
