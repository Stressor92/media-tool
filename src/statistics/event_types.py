from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class EventType(StrEnum):
    # Video
    VIDEO_CONVERTED = "video_converted"
    VIDEO_UPSCALED = "video_upscaled"
    VIDEO_MERGED = "video_merged"
    # Audio
    AUDIO_CONVERTED = "audio_converted"
    AUDIO_NORMALIZED = "audio_normalized"
    AUDIO_TAGGED = "audio_tagged"
    # Subtitles
    SUBTITLE_DOWNLOADED = "subtitle_downloaded"
    SUBTITLE_GENERATED = "subtitle_generated"
    SUBTITLE_TRANSLATED = "subtitle_translated"
    # Ebook
    EBOOK_PROCESSED = "ebook_processed"
    EBOOK_CONVERTED = "ebook_converted"
    EBOOK_ENRICHED = "ebook_enriched"
    EBOOK_COVER_ADDED = "ebook_cover_added"
    EBOOK_DEDUPLICATED = "ebook_deduplicated"
    # System
    SESSION_START = "session_start"
    SESSION_END = "session_end"
    ERROR_OCCURRED = "error_occurred"


@dataclass
class StatEvent:
    type: EventType
    timestamp: str
    duration_seconds: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)
