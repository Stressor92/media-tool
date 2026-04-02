# src/core/jellyfin/models.py
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any


class ItemType(str, Enum):
    MOVIE = "Movie"
    SERIES = "Series"
    SEASON = "Season"
    EPISODE = "Episode"
    UNKNOWN = "Unknown"


class ScanState(Enum):
    IDLE = auto()
    RUNNING = auto()
    COMPLETED = auto()
    FAILED = auto()


class MetadataIssueKind(str, Enum):
    MISSING_OVERVIEW = "missing_overview"
    MISSING_YEAR = "missing_year"
    MISSING_POSTER = "missing_poster"
    MISSING_BACKDROP = "missing_backdrop"
    WRONG_SERIES_MATCH = "wrong_series_match"
    MISSING_EPISODE_NUM = "missing_episode_number"
    DUPLICATE_ITEM = "duplicate_item"
    UNMATCHED = "unmatched"


@dataclass
class JellyfinItem:
    """Represents an item in the Jellyfin library."""

    id: str
    name: str
    item_type: ItemType
    path: str | None = None
    year: int | None = None
    overview: str | None = None
    series_id: str | None = None
    season_id: str | None = None
    index_number: int | None = None
    parent_index_number: int | None = None
    provider_ids: dict[str, str] = field(default_factory=dict)
    has_image_poster: bool = False
    has_image_backdrop: bool = False
    community_rating: float | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class LibraryInfo:
    id: str
    name: str
    locations: list[str]
    item_type: str
    item_count: int = 0


@dataclass
class ScanStatus:
    state: ScanState
    progress: float | None = None
    task_name: str | None = None
    started_at: str | None = None
    items_scanned: int = 0


@dataclass
class MetadataIssue:
    item: JellyfinItem
    kind: MetadataIssueKind
    description: str
    suggested_fix: str | None = None
    auto_fixable: bool = False


@dataclass
class RefreshResult:
    triggered: bool
    library_name: str | None = None
    item_id: str | None = None
    message: str = ""
    error: str | None = None


@dataclass
class FixResult:
    issue: MetadataIssue
    success: bool
    applied_fix: str | None = None
    error: str | None = None
