# Audiobook Module

## Scope

The audiobook domain focuses on chapter merge operations and library organization for Jellyfin-compatible structures.

## Main Components

- `merger`: detect chapter file groups and concatenate book outputs
- `organization`: move/convert audiobook files into canonical folder layout
- `metadata`: extraction helpers reused during merge/organize

## Chapter Detection Strategy

`merger` applies multiple filename regex patterns to infer:

- Book title grouping key
- Chapter ordering number

Patterns include variants such as `Book - Chapter 01`, `Book - Part 01`, and `01 - Book`.

Trade-off:

- Works on heterogeneous real-world naming
- Can misgroup atypical filenames (heuristic behavior)

## Merge Execution Model

Merge flow:

1. Collect and sort chapter files per detected book.
2. Generate temporary ffmpeg concat list.
3. Run concat with stream copy where possible.
4. Optionally preserve metadata from first chapter.
5. Cleanup temporary artifacts and validate result.

For overwrite cases, backup checkpoints can be created and rolled back on failure.

## Organization Model

Organization uses extracted metadata to build target paths:

- `Audiobooks/Author/Book/Title.ext`

Author fallback preference is narrator -> artist -> parsed fields -> unknown.

Files can be copied or converted; failures are counted and reported instead of terminating the full batch.

## Integration Points

- Uses audio conversion and metadata extraction from audio domain
- Uses progress event callbacks for long batch operations
- Uses backup system in merge overwrite paths
