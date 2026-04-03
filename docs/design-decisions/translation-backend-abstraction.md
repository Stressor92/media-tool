# Design Decision: Translation Backend Abstraction

## Context

Subtitle translation quality, speed, and model availability vary by backend and language pair.

## Decision

Introduce a translator protocol plus factory to decouple orchestration from concrete backend implementations.

Implementation anchors:

- `translator_protocol`: contract
- `translator_factory`: backend selection and construction
- `subtitle_translator`: orchestration independent of backend details

## Rationale

- Allows swapping backends without changing pipeline code
- Supports environment-specific backend availability
- Keeps chunking/reconstruction logic centralized

## Consequences

Positive:

- Portable architecture
- Easier experimentation and future backend additions

Negative:

- Behavioral variance across backends remains
- Requires backend-specific operational tuning

## Implementation-Dependent Notes

Exact backend precedence and fallback details are config- and environment-dependent.
