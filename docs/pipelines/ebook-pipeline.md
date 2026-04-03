# Ebook Pipeline

## Objective

Enrich and normalize ebook files, then optionally organize them into a library structure.

## Enrichment Pipeline

1. File identification (`BookIdentifier`)
2. Metadata fetch (`MetadataService` via provider interfaces)
3. Cover fetch (`CoverService` via provider interfaces)
4. Normalization (`EbookNormalizer`)

Normalization sub-steps:

- EPUB validation
- Optional backup checkpoint
- Metadata embedding
- Cover embedding
- TOC generation
- Backup validation and cleanup/rollback

## Organization Pipeline

1. Collect candidate files from source path
2. Identify/enrich metadata when enabled
3. Build canonical target path using naming service
4. Move/copy into library root
5. Return per-file `ProcessingResult`

## Dry Run and Safety

Command-level dry run allows planning without mutating files.

Mutating normalization operations can be backup-protected. Failures attempt rollback where backup entries exist.

## Data Quality Dependencies

Output naming quality depends on metadata quality and confidence. Fallback chains avoid total failure but can produce generic names when source data is weak.

## Trade-offs

- Deep normalization improves library consistency.
- Additional external lookups increase latency and potential network failure surface.
