from __future__ import annotations

from ..event_types import EventType, StatEvent
from ..stats_models import StatsSnapshot
from .base import BaseAggregator, ensure_daily_entry


class EbookStatsAggregator(BaseAggregator):
    _accepted = {
        EventType.EBOOK_PROCESSED,
        EventType.EBOOK_CONVERTED,
        EventType.EBOOK_ENRICHED,
        EventType.EBOOK_COVER_ADDED,
        EventType.EBOOK_DEDUPLICATED,
    }

    def accepts(self, event: StatEvent) -> bool:
        return event.type in self._accepted

    def apply(self, event: StatEvent, snapshot: StatsSnapshot) -> StatsSnapshot:
        if event.type == EventType.EBOOK_PROCESSED:
            snapshot.ebooks.processed += 1
        elif event.type == EventType.EBOOK_CONVERTED:
            snapshot.ebooks.converted += 1
        elif event.type == EventType.EBOOK_ENRICHED:
            snapshot.ebooks.metadata_enriched += 1
        elif event.type == EventType.EBOOK_COVER_ADDED:
            snapshot.ebooks.covers_added += 1
        elif event.type == EventType.EBOOK_DEDUPLICATED:
            snapshot.ebooks.deduplicated += 1

        snapshot.totals.files_processed += 1

        day_key = event.timestamp[:10]
        day = ensure_daily_entry(snapshot, day_key)
        day.files_processed += 1
        day.runtime_seconds += event.duration_seconds

        return snapshot
