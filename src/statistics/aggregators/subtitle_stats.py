from __future__ import annotations

from ..event_types import EventType, StatEvent
from ..stats_models import StatsSnapshot
from .base import BaseAggregator, ensure_daily_entry


class SubtitleStatsAggregator(BaseAggregator):
    _accepted = {EventType.SUBTITLE_DOWNLOADED, EventType.SUBTITLE_GENERATED, EventType.SUBTITLE_TRANSLATED}

    def accepts(self, event: StatEvent) -> bool:
        return event.type in self._accepted

    def apply(self, event: StatEvent, snapshot: StatsSnapshot) -> StatsSnapshot:
        if event.type == EventType.SUBTITLE_DOWNLOADED:
            snapshot.subtitles.downloaded += 1
        elif event.type == EventType.SUBTITLE_GENERATED:
            snapshot.subtitles.generated += 1
        elif event.type == EventType.SUBTITLE_TRANSLATED:
            snapshot.subtitles.translated += 1

        language = event.metadata.get("language") or event.metadata.get("target_language")
        if isinstance(language, str) and language:
            key = language.lower()
            snapshot.subtitles.by_language[key] = snapshot.subtitles.by_language.get(key, 0) + 1

        snapshot.subtitles.total_processing_time_seconds += event.duration_seconds
        snapshot.totals.files_processed += 1

        day_key = event.timestamp[:10]
        day = ensure_daily_entry(snapshot, day_key)
        day.files_processed += 1
        day.runtime_seconds += event.duration_seconds

        return snapshot
