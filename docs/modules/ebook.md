# Ebook Module

## Scope

The ebook domain covers identification, metadata enrichment, cover handling, normalization, conversion, deduplication, auditing, and library organization.

## Main Components

- Workflow: `workflow/ebook_processor`
- Metadata: `metadata/metadata_service`, provider interfaces
- Identification: `identification/book_identifier`
- Cover: cover services and provider interfaces
- Normalization: `normalization/normalizer` plus validator/embedder/TOC generation
- Organization: naming service and library organizer
- Conversion and audit helpers

## Orchestration Role of EbookProcessor

`EbookProcessor` composes identification, metadata, cover, normalization, and optional organization into command-oriented flows.

High-level flows:

- Enrich one file
- Organize library batch
- Produce per-item processing results

## Normalization Internals

`EbookNormalizer` performs staged normalization:

1. Validate EPUB structure.
2. Optionally create backup checkpoint.
3. Embed metadata.
4. Embed cover.
5. Generate TOC.
6. Validate/cleanup or rollback backup on failure.

Statistics are emitted for successful processing runs.

## Naming and Organization

Naming logic is service-based and aims for consistent Jellyfin-friendly hierarchy. Metadata quality influences target path quality; fallback chains prevent hard failure when fields are missing.

## Quality and Safety Characteristics

- Backup/rollback wraps mutation-heavy normalization paths.
- Dry-run support exists in command flows to preview actions.
- Audit and duplicate tools help converge large legacy libraries before strict organization.

## Integration Points

- CLI ebook commands map directly to processor and utility services.
- Depends on configuration for provider/API credentials and behavior toggles.
- Uses shared fuzzy matching and metadata helpers from utility layer.
