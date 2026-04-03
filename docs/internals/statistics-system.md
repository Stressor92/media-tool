# Internals: Statistics System

## Architecture

Statistics are split into collection, aggregation, and persistence responsibilities:

- `stats_collector`: event ingest
- `stats_manager`: orchestration and summaries
- `stats_models`: typed counters/timing structures
- `event_types`: canonical event taxonomy
- `stats_persistence`: durable storage with atomic-save semantics

## Event Model

Operations record typed events with optional duration and operation-specific metadata.

Examples include conversion, tagging, normalization, and ebook processing events.

## Persistence Strategy

Persistence aims to avoid partial-file corruption by using atomic write behavior for stats snapshots.

Benefits:

- Crash-safe update semantics
- Lower risk of malformed metrics state

## Operational Notes

Many domain operations treat statistics as noncritical side effects:

- Record attempt is wrapped in exception handling
- Failure to record does not fail the media operation

This keeps telemetry best-effort while preserving core operation reliability.
