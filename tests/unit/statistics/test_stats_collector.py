from __future__ import annotations

import threading

from src.statistics.event_types import EventType
from src.statistics.stats_collector import StatsCollector


def test_record_adds_event() -> None:
    collector = StatsCollector()
    collector.record(EventType.VIDEO_CONVERTED, duration_seconds=1.2)
    events = collector.get_events()
    assert len(events) == 1
    assert events[0].type == EventType.VIDEO_CONVERTED


def test_end_session_returns_and_clears_events() -> None:
    collector = StatsCollector()
    collector.start_session()
    collector.record(EventType.AUDIO_CONVERTED)

    events = collector.end_session()

    assert len(events) >= 2
    assert collector.get_events() == []


def test_thread_safety_recording() -> None:
    collector = StatsCollector()

    def _worker() -> None:
        for _ in range(100):
            collector.record(EventType.SUBTITLE_DOWNLOADED)

    threads = [threading.Thread(target=_worker) for _ in range(10)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert len(collector.get_events()) == 1000
