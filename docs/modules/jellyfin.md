# Jellyfin Module

## Scope

The Jellyfin domain inspects and repairs library metadata quality issues through API-backed operations.

## Main Components

- `client`: API communication layer
- `library_manager`: item retrieval and refresh orchestration
- `metadata_inspector`: issue detection rules
- `metadata_fixer`: auto-fix and guided-fix strategies
- `models`: item/issue/fix/scan result contracts

## Inspection Model

Inspector checks include:

- Missing overview/year/poster/backdrop
- Unmatched items (missing provider IDs)
- Missing episode numbering
- Wrong series assignment heuristics
- Duplicate item detection

Most checks are deterministic against fetched item fields; some are path-heuristic driven.

## Fix Strategy

Fixer uses issue-kind dispatch:

- Auto-fixable issues trigger forced metadata refresh
- Some issue kinds remain manual or guided (for example duplicate handling)

Trade-off:

- Safe automation for common recoverable issues
- Avoids destructive automatic actions where ambiguity is high

## Integration Points

- Exposed through dedicated CLI command group
- Can be used independently from local media processing workflows
- Depends on Jellyfin server availability and correct API credentials

## Implementation-Dependent Areas

Path parsing heuristics for year/series/episode inference are best-effort and may require manual correction on nonstandard library layouts.
