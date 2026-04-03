from __future__ import annotations

from src.statistics.aggregators.audio_stats import AudioStatsAggregator
from src.statistics.aggregators.ebook_stats import EbookStatsAggregator
from src.statistics.aggregators.subtitle_stats import SubtitleStatsAggregator
from src.statistics.aggregators.system_stats import SystemStatsAggregator
from src.statistics.aggregators.video_stats import VideoStatsAggregator
from src.statistics.event_types import EventType, StatEvent
from src.statistics.stats_models import StatsSnapshot


def test_video_aggregator_accepts_and_applies() -> None:
    aggregator = VideoStatsAggregator()
    event = StatEvent(type=EventType.VIDEO_UPSCALED, timestamp="2026-04-03T12:00:00+00:00", duration_seconds=4.0)
    snapshot = StatsSnapshot()

    assert aggregator.accepts(event)
    updated = aggregator.apply(event, snapshot)
    assert updated.video.upscaled == 1


def test_audio_aggregator_accepts_and_applies() -> None:
    aggregator = AudioStatsAggregator()
    event = StatEvent(type=EventType.AUDIO_TAGGED, timestamp="2026-04-03T12:00:00+00:00", duration_seconds=1.0)
    snapshot = StatsSnapshot()

    assert aggregator.accepts(event)
    updated = aggregator.apply(event, snapshot)
    assert updated.audio.tagged == 1


def test_subtitle_aggregator_accepts_and_applies() -> None:
    aggregator = SubtitleStatsAggregator()
    event = StatEvent(
        type=EventType.SUBTITLE_TRANSLATED,
        timestamp="2026-04-03T12:00:00+00:00",
        metadata={"target_language": "en"},
    )
    snapshot = StatsSnapshot()

    assert aggregator.accepts(event)
    updated = aggregator.apply(event, snapshot)
    assert updated.subtitles.translated == 1
    assert updated.subtitles.by_language["en"] == 1


def test_ebook_aggregator_accepts_and_applies() -> None:
    aggregator = EbookStatsAggregator()
    event = StatEvent(type=EventType.EBOOK_ENRICHED, timestamp="2026-04-03T12:00:00+00:00")
    snapshot = StatsSnapshot()

    assert aggregator.accepts(event)
    updated = aggregator.apply(event, snapshot)
    assert updated.ebooks.metadata_enriched == 1


def test_system_aggregator_accepts_and_applies() -> None:
    aggregator = SystemStatsAggregator()
    snapshot = StatsSnapshot()

    assert aggregator.accepts(StatEvent(type=EventType.SESSION_START, timestamp="2026-04-03T12:00:00+00:00"))
    snapshot = aggregator.apply(
        StatEvent(type=EventType.SESSION_START, timestamp="2026-04-03T12:00:00+00:00"), snapshot
    )
    snapshot = aggregator.apply(
        StatEvent(type=EventType.SESSION_END, timestamp="2026-04-03T12:01:00+00:00", duration_seconds=60.0), snapshot
    )
    snapshot = aggregator.apply(
        StatEvent(type=EventType.ERROR_OCCURRED, timestamp="2026-04-03T12:02:00+00:00"), snapshot
    )

    assert snapshot.system.runs == 1
    assert snapshot.system.total_runtime_seconds == 60.0
    assert snapshot.system.errors == 1
