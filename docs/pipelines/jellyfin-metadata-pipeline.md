# Jellyfin Metadata Pipeline

## Objective

Inspect Jellyfin items for metadata issues and apply safe automated fixes.

## Inspection Sequence

1. Retrieve movies, series, episodes from `LibraryManager`
2. Run issue checks in `MetadataInspector`
3. Emit typed `MetadataIssue` list

Issue categories include:

- Missing overview/year/poster/backdrop
- Unmatched items (missing provider IDs)
- Missing episode numbers
- Wrong series match heuristics
- Duplicate detection

## Fix Sequence

1. Filter auto-fixable issues
2. Dispatch fix strategy by issue kind
3. Trigger forced metadata refresh where appropriate
4. Return typed `FixResult` list

## Safety Boundaries

- Duplicate items are report-oriented, not auto-deleted.
- Series reassignment is guided and should be operator-reviewed.

## Trade-offs

- Refresh-based fixes are robust and low-risk.
- Some semantic mismatches require manual intervention despite automation.
