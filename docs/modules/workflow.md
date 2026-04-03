# Workflow Module

## Scope

The workflow domain orchestrates multi-step media processing pipelines for movie/series libraries.

## Main Components

- `runner`: executes configured step sequence
- `models`: shared context/result structures
- `steps/s01..s06`: concrete pipeline stages

## Step Contract

Each step follows a common lifecycle:

1. `should_run(context)`
2. `run(context)`
3. `post_check(context, result)`

This keeps orchestration generic while allowing domain-specific logic per stage.

## Default Stage Responsibilities

- `s01`: merge duplicate-language or related source variants
- `s02`: remux mp4 to mkv where configured
- `s03`: upscale selected low-resolution/DVD-like sources
- `s04`: re-encode selected high-resolution/Blu-ray-like sources
- `s05`: subtitle acquisition/translation handling
- `s06`: final organization in target naming/layout

Exact run conditions are configuration- and media-dependent.

## Operational Characteristics

- Sequential execution to preserve deterministic ordering
- Per-step result capture for reporting/debug
- Partial processing possible if preconditions skip specific files/stages

## Cross-Cutting Integrations

- Calls video, subtitle, translation, and organization services
- Uses backup/validation around mutating operations where enabled
- Emits statistics events for selected successful operations

## Reliability Strategy

Workflow favors explicit step boundaries and typed results to isolate failures. Failures in one stage can be surfaced with enough context to retry only affected segments.
