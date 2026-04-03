from __future__ import annotations

from ..event_types import EventType, StatEvent
from ..stats_models import StatsSnapshot
from .base import BaseAggregator, ensure_daily_entry


class VideoStatsAggregator(BaseAggregator):
    _accepted = {EventType.VIDEO_CONVERTED, EventType.VIDEO_UPSCALED, EventType.VIDEO_MERGED}

    def accepts(self, event: StatEvent) -> bool:
        return event.type in self._accepted

    def apply(self, event: StatEvent, snapshot: StatsSnapshot) -> StatsSnapshot:
        if event.type == EventType.VIDEO_CONVERTED:
            snapshot.video.converted += 1
        elif event.type == EventType.VIDEO_UPSCALED:
            snapshot.video.upscaled += 1
        elif event.type == EventType.VIDEO_MERGED:
            snapshot.video.merged += 1

        snapshot.video.total_processing_time_seconds += event.duration_seconds
        snapshot.totals.files_processed += 1

        input_res = event.metadata.get("input_resolution")
        output_res = event.metadata.get("output_resolution")
        if isinstance(input_res, str) and input_res:
            snapshot.video.input_resolutions[input_res] = snapshot.video.input_resolutions.get(input_res, 0) + 1
        if isinstance(output_res, str) and output_res:
            snapshot.video.output_resolutions[output_res] = snapshot.video.output_resolutions.get(output_res, 0) + 1

        total_video_items = max(1, snapshot.video.converted + snapshot.video.upscaled + snapshot.video.merged)
        event.metadata["seconds_per_file"] = snapshot.video.total_processing_time_seconds / total_video_items

        before_size = event.metadata.get("file_size_before_mb")
        after_size = event.metadata.get("file_size_after_mb")
        if isinstance(before_size, int | float) and isinstance(after_size, int | float) and before_size > 0:
            event.metadata["compression_ratio"] = float(after_size) / float(before_size)

        day_key = event.timestamp[:10]
        day = ensure_daily_entry(snapshot, day_key)
        day.files_processed += 1
        day.runtime_seconds += event.duration_seconds

        return snapshot
