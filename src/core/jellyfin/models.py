# src/core/jellyfin/models.py
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Optional


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
    path: Optional[str] = None
    year: Optional[int] = None
    overview: Optional[str] = None
    series_id: Optional[str] = None
    season_id: Optional[str] = None
    index_number: Optional[int] = None
    parent_index_number: Optional[int] = None
    provider_ids: dict[str, str] = field(default_factory=dict)
    has_image_poster: bool = False
    has_image_backdrop: bool = False
    community_rating: Optional[float] = None
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
    progress: Optional[float] = None
    task_name: Optional[str] = None
    started_at: Optional[str] = None
    items_scanned: int = 0


@dataclass
class MetadataIssue:
    item: JellyfinItem
    kind: MetadataIssueKind
    description: str
    suggested_fix: Optional[str] = None
    auto_fixable: bool = False


@dataclass
class RefreshResult:
    triggered: bool
    library_name: Optional[str] = None
    item_id: Optional[str] = None
    message: str = ""
    error: Optional[str] = None


@dataclass
class FixResult:
    issue: MetadataIssue
    success: bool
    applied_fix: Optional[str] = None
    error: Optional[str] = None
