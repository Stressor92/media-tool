# src/core/jellyfin/metadata_inspector.py
from __future__ import annotations

import logging
import re
from pathlib import Path

from core.jellyfin.library_manager import LibraryManager
from core.jellyfin.models import (
    ItemType,
    JellyfinItem,
    MetadataIssue,
    MetadataIssueKind,
)

logger = logging.getLogger(__name__)

_YEAR_RE = re.compile(r"\((\d{4})\)")
_EP_RE = re.compile(r"S(\d{2})E(\d{2})", re.IGNORECASE)


class MetadataInspector:
    """
    Analyses the Jellyfin library and finds metadata problems:
    - Missing posters, backdrops, descriptions
    - Unmatched items (no provider IDs)
    - Wrong series assignments (episode under wrong series)
    - Missing episode numbers
    - Duplicates (same title appears multiple times)
    """

    def __init__(self, manager: LibraryManager) -> None:
        self._manager = manager

    def inspect_movies(self, library_id: str | None = None) -> list[MetadataIssue]:
        """Checks all movies for metadata completeness."""
        movies = self._manager.get_all_items(ItemType.MOVIE, library_id)
        logger.info("Checking %d movies …", len(movies))
        issues: list[MetadataIssue] = []
        for movie in movies:
            issues.extend(self._check_movie(movie))
        return issues

    def inspect_series(self, library_id: str | None = None) -> list[MetadataIssue]:
        """Checks all series and episodes."""
        series_list = self._manager.get_all_items(ItemType.SERIES, library_id)
        episodes = self._manager.get_all_items(ItemType.EPISODE, library_id)
        logger.info("Checking %d series, %d episodes …", len(series_list), len(episodes))
        issues: list[MetadataIssue] = []
        for s in series_list:
            issues.extend(self._check_series(s))
        for ep in episodes:
            issues.extend(self._check_episode(ep, series_list))
        issues.extend(self._check_duplicates(series_list + episodes))
        return issues

    def inspect_all(self, library_id: str | None = None) -> list[MetadataIssue]:
        return self.inspect_movies(library_id) + self.inspect_series(library_id)

    # ── Check logic ──────────────────────────────────────────────────────

    def _check_movie(self, item: JellyfinItem) -> list[MetadataIssue]:
        issues: list[MetadataIssue] = []

        if not item.overview:
            issues.append(
                MetadataIssue(
                    item=item,
                    kind=MetadataIssueKind.MISSING_OVERVIEW,
                    description=f"'{item.name}': No description.",
                    suggested_fix="Force a full metadata refresh.",
                    auto_fixable=True,
                )
            )

        if not item.year:
            issues.append(
                MetadataIssue(
                    item=item,
                    kind=MetadataIssueKind.MISSING_YEAR,
                    description=f"'{item.name}': No release year.",
                    suggested_fix=self._extract_year_from_path(item.path),
                    auto_fixable=bool(item.path and _YEAR_RE.search(item.path)),
                )
            )

        if not item.has_image_poster:
            issues.append(
                MetadataIssue(
                    item=item,
                    kind=MetadataIssueKind.MISSING_POSTER,
                    description=f"'{item.name}': No poster image.",
                    auto_fixable=True,
                )
            )

        if not item.has_image_backdrop:
            issues.append(
                MetadataIssue(
                    item=item,
                    kind=MetadataIssueKind.MISSING_BACKDROP,
                    description=f"'{item.name}': No backdrop image.",
                    auto_fixable=True,
                )
            )

        if not item.provider_ids:
            issues.append(
                MetadataIssue(
                    item=item,
                    kind=MetadataIssueKind.UNMATCHED,
                    description=(f"'{item.name}': No provider IDs (TMDB/IMDB). Item was not matched by Jellyfin."),
                    auto_fixable=False,
                )
            )

        return issues

    def _check_series(self, series: JellyfinItem) -> list[MetadataIssue]:
        issues: list[MetadataIssue] = []
        if not series.overview:
            issues.append(
                MetadataIssue(
                    item=series,
                    kind=MetadataIssueKind.MISSING_OVERVIEW,
                    description=f"Series '{series.name}': No description.",
                    auto_fixable=True,
                )
            )
        if not series.has_image_poster:
            issues.append(
                MetadataIssue(
                    item=series,
                    kind=MetadataIssueKind.MISSING_POSTER,
                    description=f"Series '{series.name}': No poster.",
                    auto_fixable=True,
                )
            )
        return issues

    def _check_episode(self, ep: JellyfinItem, series_list: list[JellyfinItem]) -> list[MetadataIssue]:
        issues: list[MetadataIssue] = []

        if ep.index_number is None:
            ep_num = self._extract_episode_from_path(ep.path)
            issues.append(
                MetadataIssue(
                    item=ep,
                    kind=MetadataIssueKind.MISSING_EPISODE_NUM,
                    description=f"Episode '{ep.name}': No episode number.",
                    suggested_fix=ep_num,
                    auto_fixable=bool(ep_num),
                )
            )

        if ep.path and ep.series_id:
            path_series_name = self._extract_series_from_path(ep.path)
            assigned_series = next((s for s in series_list if s.id == ep.series_id), None)
            if path_series_name and assigned_series and path_series_name.lower() not in assigned_series.name.lower():
                issues.append(
                    MetadataIssue(
                        item=ep,
                        kind=MetadataIssueKind.WRONG_SERIES_MATCH,
                        description=(
                            f"Episode '{ep.name}' is in folder '{path_series_name}' "
                            f"but assigned to series '{assigned_series.name}'."
                        ),
                        suggested_fix=f"Reassign to: {path_series_name}",
                        auto_fixable=False,
                    )
                )

        return issues

    def _check_duplicates(self, items: list[JellyfinItem]) -> list[MetadataIssue]:
        seen: dict[str, list[JellyfinItem]] = {}
        for item in items:
            key = f"{item.name}_{item.year or ''}_{item.item_type.value}"
            seen.setdefault(key, []).append(item)

        issues: list[MetadataIssue] = []
        for _key, dupes in seen.items():
            if len(dupes) > 1:
                for item in dupes:
                    issues.append(
                        MetadataIssue(
                            item=item,
                            kind=MetadataIssueKind.DUPLICATE_ITEM,
                            description=(f"'{item.name}' appears {len(dupes)}× in the library."),
                            auto_fixable=False,
                        )
                    )
        return issues

    # ── Path helpers ─────────────────────────────────────────────────────

    @staticmethod
    def _extract_year_from_path(path: str | None) -> str | None:
        if not path:
            return None
        m = _YEAR_RE.search(path)
        return f"Take year {m.group(1)} from path." if m else None

    @staticmethod
    def _extract_episode_from_path(path: str | None) -> str | None:
        if not path:
            return None
        m = _EP_RE.search(path)
        return f"S{m.group(1)}E{m.group(2)}" if m else None

    @staticmethod
    def _extract_series_from_path(path: str | None) -> str | None:
        if not path:
            return None
        parts = Path(path).parts
        # Heuristic: the folder two levels above the file is the series
        # e.g. /media/Series/My Show/Season 01/ep.mkv → "My Show"
        if len(parts) >= 3:
            candidate = parts[-3]
            if not candidate.lower().startswith("season"):
                return candidate
        return None
