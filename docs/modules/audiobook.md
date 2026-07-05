# Audiobook Module

## Scope

The audiobook domain focuses on chapter merge operations and library organization for Jellyfin-compatible structures.

## Main Components

- `merger`: detect chapter file groups and concatenate book outputs
- `organization`: move/convert audiobook files into canonical folder layout
- `metadata`: extraction helpers reused during merge/organize

## Chapter Detection Strategy

`merger` supports two grouping strategies:

- `metadata-first` (default): group by metadata title candidates (`album`, `series`, parsed fields, then title), then use track/disc ordering.
- `filename`: group only by filename regex patterns.

For filename fallback, `merger` applies multiple regex patterns to infer:

- Book title grouping key
- Chapter ordering number

Patterns include variants such as `Book - Chapter 01`, `Book - Part 01`, and `01 - Book`.

Ordering priority in `metadata-first` mode:

1. `track_number` (+ `disc_number` when available)
2. `parsed_track_number`
3. Chapter number from filename regex
4. Stable filename order

Important ordering detail:

- When track numbers repeat across discs (for example Disc 1: 01..20 and Disc 2: 01..18), merge keeps the detected chapter sequence and does not re-sort by plain track number later.
- This prevents cross-disc interleaving such as `D1T01, D2T01, D1T02, D2T02`.

Trade-off:

- Works on heterogeneous real-world naming
- Can misgroup atypical filenames (heuristic behavior)

## Merge Execution Model

Merge flow:

1. Collect and sort chapter files per detected book.
2. Generate temporary ffmpeg concat list.
3. Run concat with audio-only mapping and format-aware encoding.
4. Optionally preserve metadata from first chapter.
5. Cleanup temporary artifacts and validate result.

Pre-merge normalization:

- Chapter candidates are deduplicated before concatenation.
- Duplicate key normalization removes trailing copy suffixes like `(1)`, `(2)`, `(3)`.
- Exact duplicates are collapsed to one representative chapter.
- If candidates for the same chapter key are not byte-identical, a deterministic conflict resolver selects one file and reports conflict count in progress output.

Container compatibility note:

- Merge maps audio stream only (`-map 0:a:0`) to avoid passing unsupported side streams (for example MJPEG cover tracks) into output containers.
- Output codec is selected by requested format (`m4a/m4b` -> AAC, `mp3` -> libmp3lame, `flac` -> flac, `ogg/opus` -> libopus).

Merge scope:

- Only detected groups with at least two chapters are merged.
- Single files are skipped intentionally.

For overwrite cases, backup checkpoints can be created and rolled back on failure.

## Organization Model

Organization uses extracted metadata to build target paths:

- `Audiobooks/Author-Title-Year-Language/Title.ext`

When conversion is enabled, target extension follows requested format (for example `--format m4b`).
If language metadata is missing, `de` is used as default language token.

Author fallback preference is narrator -> artist -> parsed fields -> unknown.

Files can be copied or converted; failures are counted and reported instead of terminating the full batch.

## CLI Usage Notes

- Organize command uses positional source/target directories:
	- `media-tool audiobook organize <source_dir> <target_dir> --format m4b`
- Collect command recursively scans subfolders and organizes into same flat folder scheme:
	- `media-tool audiobook collect <source_root> <target_dir> --format m4b`
- Remove-silence command removes long silent sections in a file or library tree:
	- `media-tool audiobook remove-silence <source> <target> --min-silence-seconds 10`
- Merge command uses positional source/target directories:
	- `media-tool audiobook merge <source_dir> <target_dir> --format m4b --grouping metadata-first`
- Use `--dry-run` for safe preview before merge execution.

## Silence Cleanup

- Uses ffmpeg `silenceremove` over full stream, not only start/end trim.
- Default behavior removes silent sections longer than 10 seconds.
- Threshold and duration are configurable via CLI options.

## Integration Points

- Uses audio conversion and metadata extraction from audio domain
- Uses progress event callbacks for long batch operations
- Uses backup system in merge overwrite paths
