# Metadata Module

## Scope

The metadata domain enriches **movie files** using TMDB-backed lookup and filesystem-friendly output generation. Its main output is a set of local sidecar assets such as:

- `.nfo` files
- poster and fanart images
- structured metadata results for later reporting or organization

This module is separate from the ebook metadata system under `core/ebook`.

---

## Key Components

| File | Role |
|---|---|
| `title_parser.py` | derive a clean title and optional year from folder/file names |
| `tmdb_provider.py` | search TMDB and fetch detailed movie metadata |
| `match_selector.py` | choose a candidate automatically or interactively |
| `metadata_pipeline.py` | orchestrate parse -> search -> select -> write |
| `nfo_writer.py` | emit Jellyfin/Kodi-compatible `.nfo` files |
| `artwork_downloader.py` | fetch poster/fanart/banner assets |
| `models.py` | result/status types such as `PipelineResult` and `MetadataStatus` |

---

## Parsing Strategy

The entry heuristic is `parse_title(path)` in `title_parser.py`.

It attempts to recover a usable search query by:

1. preferring the parent folder name when it looks more canonical
2. extracting the last detected year matching `19xx` / `20xx`
3. stripping common release tags such as:
   - `BluRay`, `WEB-DL`, `DVDRip`
   - `720p`, `1080p`, `2160p`
   - `x264`, `x265`, `HEVC`, `AAC`, `DTS`
   - language markers like `German`, `English`, `MULTI`
4. normalizing separators like `.` and `_` into spaces

This parser is intentionally conservative: it aims to improve search quality without claiming guaranteed title extraction.

---

## Selection Model

The movie metadata flow is simpler than a full ranking engine.

### Automatic mode

`MatchSelector` in `SelectionMode.AUTO` currently selects the **first TMDB result** returned by the provider.

### Interactive mode

`SelectionMode.INTERACTIVE` renders a numbered candidate list and asks the operator to choose or skip.

> This means the quality of automatic selection is partly delegated to TMDB's search ordering rather than a custom local confidence score.

---

## `MetadataPipeline` Execution

`MetadataPipeline.process_file()` performs the following sequence:

1. derive `movie_dir` and expected NFO path
2. skip immediately when an NFO already exists and overwrite is disabled
3. parse title/year from the video filename
4. call `TmdbProvider.search(...)`
5. select a candidate through `MatchSelector`
6. optionally short-circuit for `dry_run`
7. fetch full movie metadata for the selected TMDB id
8. write an NFO file and download configured artwork types
9. return a `PipelineResult`

The batch entrypoint `process_directory()` applies the same logic to supported video extensions (`.mkv`, `.mp4`, `.avi`).

---

## External Dependencies

- **TMDB API** for search and detailed movie metadata
- local filesystem writes for `.nfo` and artwork assets

The module does not perform video mutations itself; it only adds metadata sidecars.

---

## Failure Semantics

The metadata layer returns explicit statuses such as:

- `SUCCESS`
- `SKIPPED`
- `NOT_FOUND`
- `FAILED`

Typical non-success cases include:

- no TMDB match found
- operator skipped selection in interactive mode
- output already exists and overwrite is disabled
- artwork or NFO writing failed

This makes metadata enrichment safe to run repeatedly over large libraries.

---

## Relationship to Other Modules

The metadata module feeds into:

- library organization and naming expectations
- audit/reporting around missing metadata assets
- Jellyfin-compatible local sidecar generation

It is adjacent to but distinct from:

- `core.jellyfin` for server-side maintenance
- `core.ebook.metadata` for book enrichment
