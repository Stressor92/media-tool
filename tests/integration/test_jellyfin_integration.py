# tests/integration/test_jellyfin_integration.py
"""
Integration tests against a live Jellyfin instance.

Requirements:
  MEDIA_TOOL_INTEGRATION_TESTS=1
  Jellyfin running and [jellyfin] configured in media-tool.toml.
"""
from __future__ import annotations

import os

import pytest

from core.jellyfin.client import JellyfinClient
from core.jellyfin.library_manager import LibraryManager
from core.jellyfin.models import ScanState


def _get_jellyfin_config() -> tuple[str, str]:
    """Returns (base_url, api_key) from config or raises pytest.skip."""
    try:
        from utils.config import get_config

        cfg = get_config()
        jf = cfg.jellyfin
        base_url = jf.base_url
        api_key = jf.api_key or ""
        if not base_url or not api_key:
            pytest.skip("No Jellyfin base_url/api_key configured in media-tool.toml.")
    except Exception:
        pytest.skip("Could not load config for Jellyfin integration tests.")
    return base_url, api_key


@pytest.fixture(scope="module")
def live_manager() -> LibraryManager:
    pytest.importorskip("requests")
    _ = os.environ.get("MEDIA_TOOL_INTEGRATION_TESTS") or pytest.skip(
        "Set MEDIA_TOOL_INTEGRATION_TESTS=1 to run integration tests."
    )
    base_url, api_key = _get_jellyfin_config()
    client = JellyfinClient(base_url, api_key)
    return LibraryManager(client)


@pytest.mark.integration
class TestJellyfinLive:
    def test_ping_succeeds(self, live_manager: LibraryManager) -> None:
        assert live_manager.ping() is True

    def test_get_server_info_has_version(self, live_manager: LibraryManager) -> None:
        info = live_manager.get_server_info()
        assert "Version" in info

    def test_get_libraries_returns_list(self, live_manager: LibraryManager) -> None:
        libs = live_manager.get_libraries()
        assert isinstance(libs, list)
        assert len(libs) > 0

    def test_libraries_have_names(self, live_manager: LibraryManager) -> None:
        libs = live_manager.get_libraries()
        for lib in libs:
            assert lib.name

    def test_scan_status_is_valid_state(self, live_manager: LibraryManager) -> None:
        status = live_manager.get_scan_status()
        assert status.state in list(ScanState)

    def test_search_returns_list(self, live_manager: LibraryManager) -> None:
        results = live_manager.search_items("a", limit=5)
        assert isinstance(results, list)

    def test_refresh_all_triggers_without_error(
        self, live_manager: LibraryManager
    ) -> None:
        result = live_manager.refresh_all()
        assert result.triggered is True
        assert result.error is None
