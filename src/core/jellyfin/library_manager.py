# src/core/jellyfin/library_manager.py
from __future__ import annotations

import logging
import time
from collections.abc import Mapping
from pathlib import Path

from core.jellyfin.client import JellyfinClient
from core.jellyfin.models import (
    ItemType,
    JellyfinItem,
    LibraryInfo,
    RefreshResult,
    ScanState,
    ScanStatus,
)

logger = logging.getLogger(__name__)

_SCAN_TASK_NAMES = {
    "RefreshLibrary",
    "Scan media library",
    "Library Scan",
}


class LibraryManager:
    """Manages library scans, refresh calls, and item lookups."""

    def __init__(self, client: JellyfinClient) -> None:
        self._client = client

    # ── Connection ───────────────────────────────────────────────────────

    def ping(self) -> bool:
        return self._client.ping()

    def get_server_info(self) -> dict[str, object]:
        result: dict[str, object] = self._client.get("/System/Info")
        return result

    # ── Library Refresh ──────────────────────────────────────────────────

    def refresh_all(self) -> RefreshResult:
        """Triggers a full library scan (equivalent to Dashboard → Refresh)."""
        try:
            self._client.post("/Library/Refresh")
            logger.info("Full library refresh triggered.")
            return RefreshResult(triggered=True, message="Full refresh started.")
        except Exception as exc:
            return RefreshResult(triggered=False, error=str(exc), message="Refresh failed.")

    def refresh_library(self, library_id: str) -> RefreshResult:
        """Refreshes a single virtual library."""
        try:
            self._client.post(
                f"/Items/{library_id}/Refresh",
                params={
                    "Recursive": True,
                    "ImageRefreshMode": "Default",
                    "MetadataRefreshMode": "Default",
                    "ReplaceAllImages": False,
                    "ReplaceAllMetadata": False,
                },
            )
            return RefreshResult(
                triggered=True,
                item_id=library_id,
                message=f"Library {library_id} refreshed.",
            )
        except Exception as exc:
            return RefreshResult(triggered=False, error=str(exc))

    def refresh_item(self, item_id: str, *, replace_metadata: bool = False) -> RefreshResult:
        """Refreshes a single item (movie, series, episode)."""
        try:
            self._client.post(
                f"/Items/{item_id}/Refresh",
                params={
                    "Recursive": True,
                    "ImageRefreshMode": "FullRefresh" if replace_metadata else "Default",
                    "MetadataRefreshMode": "FullRefresh" if replace_metadata else "Default",
                    "ReplaceAllImages": replace_metadata,
                    "ReplaceAllMetadata": replace_metadata,
                },
            )
            return RefreshResult(triggered=True, item_id=item_id, message=f"Item {item_id} refreshed.")
        except Exception as exc:
            return RefreshResult(triggered=False, error=str(exc))

    def refresh_path(self, path: Path) -> RefreshResult:
        """
        Finds the virtual library that contains the given path
        and triggers only that library's refresh.
        """
        library = self._find_library_for_path(path)
        if library:
            logger.info("Refresh triggered for library '%s'.", library.name)
            return self.refresh_library(library.id)
        logger.warning("No matching library found for %s — triggering full refresh.", path)
        return self.refresh_all()

    # ── Scan Status ──────────────────────────────────────────────────────

    def get_scan_status(self) -> ScanStatus:
        """Returns the current library scan status."""
        try:
            tasks = self._client.get("/ScheduledTasks")
        except Exception as exc:
            logger.warning("Could not retrieve scan status: %s", exc)
            return ScanStatus(state=ScanState.FAILED)

        for task in tasks:
            name = task.get("Name", "")
            if name in _SCAN_TASK_NAMES or "library" in name.lower():
                state_str = task.get("State", "Idle")
                state = {
                    "Running": ScanState.RUNNING,
                    "Idle": ScanState.IDLE,
                    "Completed": ScanState.COMPLETED,
                }.get(state_str, ScanState.IDLE)

                return ScanStatus(
                    state=state,
                    progress=task.get("CurrentProgressPercentage"),
                    task_name=name,
                    items_scanned=task.get("CurrentProgress", 0),
                )

        return ScanStatus(state=ScanState.IDLE)

    def wait_for_scan(self, timeout_seconds: int = 300, poll_interval: int = 5) -> ScanStatus:
        """Blocks until the scan finishes or the timeout is reached."""
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            status = self.get_scan_status()
            if status.state in (ScanState.IDLE, ScanState.COMPLETED):
                return status
            logger.info("Scan in progress … %.1f%%", status.progress or 0.0)
            time.sleep(poll_interval)
        return ScanStatus(
            state=ScanState.FAILED,
            task_name=f"Timeout after {timeout_seconds} seconds",
        )

    # ── Item Lookup ──────────────────────────────────────────────────────

    def get_libraries(self) -> list[LibraryInfo]:
        """Returns all virtual libraries."""
        try:
            data = self._client.get("/Library/VirtualFolders")
        except Exception:
            return []

        libs: list[LibraryInfo] = []
        for folder in data:
            libs.append(
                LibraryInfo(
                    id=folder.get("ItemId", ""),
                    name=folder.get("Name", "Unknown"),
                    locations=folder.get("Locations", []),
                    item_type=folder.get("CollectionType", "unknown"),
                    item_count=folder.get("ItemCount", 0),
                )
            )
        return libs

    def search_items(
        self,
        query: str,
        item_types: list[ItemType] | None = None,
        limit: int = 20,
    ) -> list[JellyfinItem]:
        params: dict[str, object] = {
            "searchTerm": query,
            "Limit": limit,
            "Recursive": True,
            "Fields": "Path,ProviderIds,Overview,ImageTags,BackdropImageTags",
        }
        if item_types:
            params["IncludeItemTypes"] = ",".join(t.value for t in item_types)
        try:
            data = self._client.get("/Items", params=params)
            return [self._parse_item(i) for i in data.get("Items", [])]
        except Exception:
            return []

    def get_item(self, item_id: str) -> JellyfinItem | None:
        try:
            data = self._client.get(
                f"/Items/{item_id}",
                params={"Fields": "Path,ProviderIds,Overview,ImageTags,BackdropImageTags"},
            )
            return self._parse_item(data)
        except Exception:
            return None

    def get_all_items(
        self,
        item_type: ItemType,
        library_id: str | None = None,
    ) -> list[JellyfinItem]:
        params: dict[str, object] = {
            "IncludeItemTypes": item_type.value,
            "Recursive": True,
            "Fields": "Path,ProviderIds,Overview,ImageTags,BackdropImageTags",
            "Limit": 10_000,
        }
        if library_id:
            params["ParentId"] = library_id
        try:
            data = self._client.get("/Items", params=params)
            return [self._parse_item(i) for i in data.get("Items", [])]
        except Exception:
            return []

    # ── Internal helpers ─────────────────────────────────────────────────

    def _find_library_for_path(self, path: Path) -> LibraryInfo | None:
        path_str = str(path).replace("\\", "/")
        for lib in self.get_libraries():
            for loc in lib.locations:
                if path_str.startswith(loc.replace("\\", "/")):
                    return lib
        return None

    @staticmethod
    def _parse_item(raw: Mapping[str, object]) -> JellyfinItem:
        image_tags = raw.get("ImageTags") or {}
        backdrop_tags = raw.get("BackdropImageTags") or []
        raw_type = raw.get("Type", "Unknown")
        if raw_type in ItemType._value2member_map_:
            item_type = ItemType(raw_type)
        else:
            item_type = ItemType.UNKNOWN
        provider_ids: dict[str, str] = {}
        raw_pids = raw.get("ProviderIds")
        if isinstance(raw_pids, dict):
            provider_ids = {str(k): str(v) for k, v in raw_pids.items()}
        has_poster = isinstance(image_tags, dict) and "Primary" in image_tags
        return JellyfinItem(
            id=str(raw.get("Id", "")),
            name=str(raw.get("Name", "")),
            item_type=item_type,
            path=raw.get("Path"),  # type: ignore[arg-type]
            year=raw.get("ProductionYear"),  # type: ignore[arg-type]
            overview=raw.get("Overview"),  # type: ignore[arg-type]
            series_id=raw.get("SeriesId"),  # type: ignore[arg-type]
            season_id=raw.get("SeasonId"),  # type: ignore[arg-type]
            index_number=raw.get("IndexNumber"),  # type: ignore[arg-type]
            parent_index_number=raw.get("ParentIndexNumber"),  # type: ignore[arg-type]
            provider_ids=provider_ids,
            has_image_poster=has_poster,
            has_image_backdrop=bool(backdrop_tags),
            community_rating=raw.get("CommunityRating"),  # type: ignore[arg-type]
            raw=dict(raw),
        )
