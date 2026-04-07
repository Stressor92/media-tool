# Movie Pipeline

## Scope

This document describes the **actual default movie workflow** built by `core.workflow.runner.build_movie_pipeline()` and exposed by `workflow movies`.

> The current pipeline contains **six ordered steps**. Movie metadata enrichment is currently handled separately by the `metadata` module and is not part of this runner.

---

## Execution Graph

```mermaid
flowchart LR
    A[Source directory] --> B[s01 merge language dupes]
    B --> C[s02 mp4 to mkv]
    C --> D[s03 upscale dvd]
    D --> E[s04 encode bluray]
    E --> F[s05 subtitles]
    F --> G[s06 organize]
    G --> H[Output library]
```

---

## Shared Context

All steps operate on a `WorkflowContext`:

- `source_dir` — raw incoming media root
- `output_dir` — final library destination
- `working_files` — current transformed outputs
- `metadata` — step-to-step scratch state
- `dry_run` — preview mode
- `stop_on_failure` — abort policy

The key design choice is that each step updates `working_files` so the next stage operates on the latest output set.

---

## Step-by-Step Behavior

### 1. `s01_merge_language_dupes`

Looks for duplicate title groups with language suffixes in filenames and merges them into a single MKV with multiple streams.

**Precondition:** at least one language-duplicate group exists.

**Output effect:** replaces the original grouped files with one `.merged.mkv` per detected title group.

### 2. `s02_mp4_to_mkv`

Performs a lossless remux of remaining MP4 files into MKV.

**Precondition:** at least one MP4 remains in the current working set.

**Output effect:** replaces each MP4 with a corresponding MKV.

### 3. `s03_upscale_dvd`

Detects low-resolution or DVD-like sources and runs the DVD upscale pipeline using the `dvd-hq` profile.

**Precondition:** the file probes as DVD-like (for example `height <= 576` or DVD-ish filename hints).

**Output effect:** replaces source files with new HD HEVC outputs.

### 4. `s04_encode_bluray`

Targets high-bitrate Blu-ray/remux-like MKVs and re-encodes them to H.265 with a conservative fixed profile.

**Precondition:** high-bitrate/high-resolution input that is not already HEVC/AV1.

**Output effect:** produces `[h265]` suffixed outputs and replaces the originals in `working_files`.

### 5. `s05_subtitles`

Checks for files that have only English audio and no relevant German/English subtitle streams, then tries to fetch subtitles from OpenSubtitles.

**Precondition:** subtitle-eligible files exist and an OpenSubtitles API key is configured.

**Output effect:** subtitle streams may be muxed into the existing MKV. Files that still need a Whisper fallback are reported as partial work; the code comments note that the Whisper fallback is not yet fully integrated here.

### 6. `s06_organize`

Moves the final working files into the target output structure:

```text
<output_dir>/<stem>/<stem><suffix>
```

**Precondition:** `working_files` is non-empty.

**Output effect:** finalizes library placement for Jellyfin-style browsing.

---

## Error Handling Strategy

The workflow engine distinguishes between:

- `SUCCESS`
- `SKIPPED`
- `FAILED`
- `PARTIAL`

If `stop_on_failure` is true (default), the runner stops on the first failed step. If the CLI sets `--keep-going`, later steps may still run.

This allows the same pipeline to serve both:

- strict production-style automation, and
- partial salvage runs over mixed-quality input libraries

---

## Rollback and Safety

The workflow itself does not own backup logic, but many of the underlying operations it calls do:

- video remux and merge
- DVD upscale / re-encode
- output validation and rollback

That means the pipeline benefits from safety guarantees without embedding rollback code into each step definition.

---

## Performance Considerations

The movie workflow is intentionally **sequential**.

Reasons:

- later steps depend on earlier outputs
- move/replace semantics are easier to reason about in order
- failures are easier to localize to a single step
- backup and cleanup logic is easier to validate

This reduces throughput relative to a fully parallel design but significantly improves reproducibility and operational safety.