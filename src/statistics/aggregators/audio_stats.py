from __future__ import annotations

from ..event_types import EventType, StatEvent
from ..stats_models import StatsSnapshot
from .base import BaseAggregator, ensure_daily_entry


class AudioStatsAggregator(BaseAggregator):
    _accepted = {EventType.AUDIO_CONVERTED, EventType.AUDIO_NORMALIZED, EventType.AUDIO_TAGGED}

    def accepts(self, event: StatEvent) -> bool:
        return event.type in self._accepted

    def apply(self, event: StatEvent, snapshot: StatsSnapshot) -> StatsSnapshot:
        if event.type == EventType.AUDIO_CONVERTED:
            snapshot.audio.converted += 1
        elif event.type == EventType.AUDIO_NORMALIZED:
            snapshot.audio.normalized += 1
        elif event.type == EventType.AUDIO_TAGGED:
            snapshot.audio.tagged += 1

        snapshot.audio.total_processing_time_seconds += event.duration_seconds
        snapshot.totals.files_processed += 1

        day_key = event.timestamp[:10]
        day = ensure_daily_entry(snapshot, day_key)
        day.files_processed += 1
        day.runtime_seconds += event.duration_seconds
        return snapshot
