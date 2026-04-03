# Metadata Module

## Scope

The metadata domain identifies title/year candidates, queries providers, and selects the best match for enrichment and naming use cases.

## Main Components

- `metadata_pipeline`: orchestration from parse to provider lookup to final selection
- `title_parser`: heuristic parsing of filename/title inputs
- `match_selector`: scoring and best-candidate selection policy

## Pipeline Structure

Conceptual stages:

1. Parse raw input names into normalized query tokens.
2. Query one or more metadata sources.
3. Score candidates against parsed hints and confidence signals.
4. Return selected match plus alternatives/context.

## Matching Strategy

Selection logic balances:

- Similarity/confidence
- Year/title consistency
- Source quality signals (implementation-dependent)

Trade-off:

- Strict selection reduces false positives
- Strict thresholds increase no-match outcomes

## Integration Points

- Used by video and ebook workflows for enrichment and organization naming
- Feeds audit/reporting with expected metadata fields
- Often consumed before any destructive file operation

## Failure and Ambiguity Handling

When confidence is low or candidates conflict, callers should treat results as uncertain. In several flows this means skip or require additional operator intent rather than forced write.
