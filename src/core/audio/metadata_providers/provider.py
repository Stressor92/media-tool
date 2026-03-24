from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class TrackMetadata:
    """Standardized track metadata from any provider."""
    title: str
    artist: str
    album: str
    musicbrainz_id: Optional[str] = None
    acoustid_id: Optional[str] = None
    album_artist: Optional[str] = None
    year: Optional[int] = None
    track_number: Optional[int] = None
    total_tracks: Optional[int] = None
    disc_number: Optional[int] = None
    genre: Optional[str] = None
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
    ) -> List[TrackMatch]:
        """Search for tracks matching the fingerprint."""
        ...

    @abstractmethod
    def lookup_by_id(
        self,
        track_id: str,
    ) -> Optional[TrackMetadata]:
        """Get metadata for a specific track ID."""
        ...
