from __future__ import annotations

from src.statistics.event_types import EventType, StatEvent


def test_event_types_are_unique() -> None:
    values = [event.value for event in EventType]
    assert len(values) == len(set(values))


def test_stat_event_minimal_creation() -> None:
    event = StatEvent(type=EventType.SESSION_START, timestamp="2026-04-03T12:00:00+00:00")
    assert event.duration_seconds == 0.0
    assert event.metadata == {}
