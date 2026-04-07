# Statistics Module

## Purpose

The statistics subsystem provides **best-effort operational telemetry** for media-tool runs. It is designed to answer questions such as:

- how many files were converted, tagged, translated, or enriched?
- how long did recent sessions run?
- what aggregate activity has the tool performed over time?

It is explicitly **non-critical**: telemetry failures should not stop media processing.

---

## Main Components

| File | Role |
|---|---|
| `stats_collector.py` | in-memory event collection during a process/session |
| `stats_manager.py` | load, aggregate, save, and reset the persisted snapshot |
| `event_types.py` | `EventType` enum and `StatEvent` contract |
| `stats_models.py` | persisted snapshot model |
| `stats_persistence.py` | on-disk load/save/backup behavior |
| `aggregators/*` | apply event types onto the correct section of the snapshot |

---

## Runtime Lifecycle

The lifecycle is initialized from `src/cli/main.py` inside the global Typer callback.

### Startup

When `config.statistics.enabled` is true:

1. a `StatsManager` is created
2. persisted state is loaded via `manager.load()`
3. the manager is registered with `src.statistics.init(manager)`
4. `statistics.get_collector().start_session()` records `SESSION_START`

### Shutdown

An `atexit` callback then:

1. ends the session (`SESSION_END`)
2. retrieves all buffered events
3. aggregates them into the snapshot
4. saves the snapshot to disk

This makes statistics collection effectively process-scoped.

---

## Event Taxonomy

`EventType` currently includes events for:

- **video**: converted, upscaled, merged
- **audio**: converted, normalized, tagged
- **subtitles**: downloaded, generated, translated
- **ebooks**: processed, converted, enriched, cover added, deduplicated
- **system**: session start/end, error occurred
- **backup**: created, rolled back, cleaned

### Implementation note

The current `StatsManager` loads aggregators for video, audio, subtitle, ebook, and system events. Unknown or currently unsupported event types are ignored with a debug log message rather than failing the run.

---

## Aggregation Model

`StatsManager.aggregate(events)` loops over the recorded event list and lets each registered aggregator decide whether it accepts the event.

This design has two useful properties:

- event production remains simple at the call site
- persistence logic stays centralized and strongly typed

It also means new telemetry categories can be added incrementally by adding a new aggregator instead of rewriting the manager.

---

## Safety Characteristics

The subsystem is intentionally defensive:

- event recording is wrapped in `try/except`
- collector operations are protected by a thread lock
- telemetry exceptions are downgraded to debug logging
- resets require explicit confirmation

This aligns with the repository-wide rule that **observability must not become a single point of failure**.

---

## Integration Points

Statistics events are emitted opportunistically from many domains, including:

- video conversion, merge, and upscale flows
- subtitle translation and download paths
- ebook enrichment and normalization
- backup lifecycle operations

Because the statistics API is lightweight, the instrumentation footprint in domain code stays minimal.