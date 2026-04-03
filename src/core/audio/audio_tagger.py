from __future__ import annotations

import logging
import time

from src.statistics import get_collector
from src.statistics.event_types import EventType

from core.audio.metadata_providers.acoustid_provider import AcoustIDProvider
from core.audio.metadata_providers.provider import TrackMatch, TrackMetadata
from utils.mutagen_tagger import MutagenTagger

logger = logging.getLogger(__name__)


class AudioTagger:
    """High-level orchestrator for audio metadata discovery and tagging."""

    def __init__(self, acoustid_api_key: str):
        self.provider = AcoustIDProvider(acoustid_api_key)

    def identify(self, file_path: str) -> list[TrackMatch]:
        return self.provider.from_audio_file(file_path, self.provider.acoustid_api_key)

    def auto_tag(
        self,
        file_path: str,
        force: bool = False,
        min_confidence: float = 0.7,
    ) -> TrackMetadata | None:
        start = time.perf_counter()
        matches = self.identify(file_path)
        if not matches:
            return None

        best = matches[0]
        if best.confidence < min_confidence:
            return None

        metadata = best.metadata
        MutagenTagger.write_metadata(file_path, metadata, force=force)
        try:
            get_collector().record(EventType.AUDIO_TAGGED, duration_seconds=time.perf_counter() - start)
        except Exception:
            logger.debug("Stats recording failed", exc_info=True)
        return metadata

    @staticmethod
    def best_match(matches: list[TrackMatch]) -> TrackMatch | None:
        if not matches:
            return None
        return max(matches, key=lambda m: m.confidence)
