# Design Decision: Naming Strategy and Library Layout

## Context

Media libraries must be organized in a deterministic structure for downstream systems such as Jellyfin.

## Decision

Centralize naming and path-generation logic in dedicated services/helpers instead of inline ad-hoc path assembly.

Implementation anchors:

- Jellyfin naming helpers in utility layer
- Ebook naming service in organization domain
- Workflow organization stage (`s06_organize`) as final canonicalizer

## Rationale

- Single place to evolve sanitization and path rules
- Reduces drift across domains/commands
- Improves consistency for indexing systems

## Consequences

Positive:

- Stable, predictable target structure
- Easier maintenance and testing of naming rules

Negative:

- Generic fallback names when metadata is incomplete
- Heuristic naming can still require manual correction on edge cases

## Implementation-Dependent Notes

Exact field precedence and sanitization outcomes differ slightly by domain (video, audiobook, ebook) and available metadata quality.
