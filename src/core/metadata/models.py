from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Any


class ArtworkType(str, Enum):
    POSTER = "poster"
    FANART = "fanart"
    BANNER = "banner"
    LOGO = "logo"
    THUMB = "thumb"
    DISC = "disc"


class MetadataStatus(Enum):
    SUCCESS = auto()
    SKIPPED = auto()
    NOT_FOUND = auto()
    NEEDS_SELECTION = auto()
    FAILED = auto()


@dataclass
class TmdbSearchResult:
    tmdb_id: int
    title: str
    original_title: str
    year: int | None
    overview: str
    popularity: float
    vote_average: float
    vote_count: int
    poster_path: str | None
    backdrop_path: str | None
    genre_ids: list[int] = field(default_factory=list)


@dataclass
class ActorInfo:
    name: str
    role: str
    order: int
    profile_path: str | None
    tmdb_id: int | None = None


@dataclass
class CrewMember:
    name: str
    job: str
    department: str


@dataclass
class MovieMetadata:
    tmdb_id: int
    imdb_id: str | None
    title: str
    original_title: str
    sort_title: str
    year: int | None
    release_date: str | None
    overview: str
    tagline: str
    runtime: int | None
    vote_average: float
    vote_count: int
    popularity: float
    mpaa_rating: str | None
    genres: list[str] = field(default_factory=list)
    studios: list[str] = field(default_factory=list)
    countries: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    cast: list[ActorInfo] = field(default_factory=list)
    crew: list[CrewMember] = field(default_factory=list)
    collections: list[str] = field(default_factory=list)
    trailer_url: str | None = None
    poster_path: str | None = None
    backdrop_path: str | None = None
    available_posters: list[dict[str, Any]] = field(default_factory=list)
    available_backdrops: list[dict[str, Any]] = field(default_factory=list)
    available_logos: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class ArtworkFile:
    type: ArtworkType
    url: str
    local_path: Path
    width: int = 0
    height: int = 0
    language: str | None = None
    vote_average: float = 0.0


@dataclass
class PipelineResult:
    status: MetadataStatus
    source_path: Path
    movie_dir: Path
    metadata: MovieMetadata | None = None
    nfo_path: Path | None = None
    artwork_files: list[ArtworkFile] = field(default_factory=list)
    search_results: list[TmdbSearchResult] = field(default_factory=list)
    error: str | None = None
    skipped_reason: str | None = None
