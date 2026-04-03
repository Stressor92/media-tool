# Audit Module

## Scope

The audit domain scans media collections for quality/compliance issues and returns structured findings.

## Main Components

- `auditor`: orchestrates checks against target libraries
- `check_registry`: check discovery and dispatch
- `models`: finding/report contracts (severity, kind, summary)

## Audit Execution Model

1. Discover target files/items.
2. Run registered checks.
3. Aggregate findings by kind/severity.
4. Produce report model and optional summary output.

The design supports additive checks without rewriting orchestration logic.

## Findings Model

Typed finding/report structures allow:

- CLI-friendly output tables
- Machine-readable post-processing
- Stable severity semantics across check types

## Trade-offs

- Generic registry increases extensibility
- Requires disciplined check metadata to keep reports coherent

## Integration Points

- Used by dedicated CLI audit commands
- Supports quality gates before organization or destructive conversion
- Can complement Jellyfin inspections for server-side metadata quality
