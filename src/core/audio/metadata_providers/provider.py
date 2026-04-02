from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class TrackMetadata:
    """Standardized track metadata from any provider."""

    title: str
    artist: str
    album: str
    musicbrainz_id: str | None = None
    acoustid_id: str | None = None
    album_artist: str | None = None
    year: int | None = None
    track_number: int | None = None
    total_tracks: int | None = None
    disc_number: int | None = None
    genre: str | None = None
    confidence_score: float = 0.0


@dataclass
class TrackMatch:
    """Potential metadata match from a provider."""

    metadata: TrackMetadata
    confidence: float
    source: str


class MetadataProvider(ABC):
    """Abstract base for metadata sources."""

    @abstractmethod
    def lookup_by_fingerprint(
        self,
        fingerprint: str,
        duration: float,
    ) -> list[TrackMatch]:
        """Search for tracks matching the fingerprint."""
        ...

    @abstractmethod
    def lookup_by_id(
        self,
        track_id: str,
    ) -> TrackMetadata | None:
        """Get metadata for a specific track ID."""
        ...
