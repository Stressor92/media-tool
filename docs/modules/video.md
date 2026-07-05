# Video Module

## Responsibilities

The video domain is responsible for **technical transformation of movie files** before they are organized into a library. It covers:

- lossless remuxing (`.mp4` → `.mkv`)
- dual-audio merging of language variants
- DVD upscaling and Blu-ray re-encoding
- media inspection and subtitle-related helpers
- trailer handling and Whisper-based subtitle generation support

The module is intentionally split into small services that return typed results instead of interacting with the CLI directly.

---

## Key Components

| File | Role |
|---|---|
| `converter.py` | lossless container remux with backup/validation |
| `merger.py` | combine German and English sources into a dual-audio MKV |
| `upscaler.py` | H.265 DVD upscale pipeline with filter-chain construction |
| `transcoder.py` | source-resolution H.265 transcode for BR rip style workflows |
| `upscale_profiles.py` | named encoding presets such as `dvd`, `dvd-hq`, `archive`, `anime` |
| `hardware_detector.py` | probe NVENC / AMF / QSV availability and choose the best encoder |
| `encoder_profile_builder.py` | translate profile intent into ffmpeg argument fragments |
| `inspector.py` | ffprobe-backed media inspection for inventory/export workflows |
| `trailer_search.py`, `trailer_downloader.py` | trailer discovery and ingestion |
| `whisper_engine.py`, `subtitle_generator.py` | local subtitle/transcription support |

---

## Internal Workflows

### 1. Lossless remux

`convert_mp4_to_mkv()` in `converter.py` performs a stream-copy remux:

1. validate source and target conditions
2. build an ffmpeg `-map 0 -c copy` command
3. create a backup checkpoint when possible
4. run ffmpeg through `utils.ffmpeg_runner.run_ffmpeg()`
5. validate the output and cleanup or rollback the backup
6. emit `EventType.VIDEO_CONVERTED`

This operation is optimized for **container normalization without re-encoding**.

### 2. Dual-audio merge

`merge_dual_audio()` in `merger.py` expects a German and an English source and produces a single MKV with:

- video from the German source
- audio tracks copied from both sources
- stream metadata set to `deu` / `eng`

The helper `detect_language_files()` identifies the pair from filename suffix patterns such as `-de`, `_en`, `(en)`, etc.

For CLI batch usage (`media-tool merge batch`), series-like names are normalized as well:

- episode patterns like `Show - S01E02 - en.mp4` and `Show - S0102 - de.mp4` are treated as series episodes
- outputs are written to `Show/Season 01/Show -S01E02.mkv`
- single-file groups set audio metadata from probed stream language when available (fallback to filename suffix)

### 3. DVD upscale pipeline

`upscale_dvd()` is the most sophisticated path in the module. It:

1. probes the source via `ffprobe`
2. estimates DAR/SAR and optionally crop values
3. disables crop detection for anime-like names
4. builds a filter chain (`deinterlace -> crop -> gradfun -> scale -> eq -> unsharp -> format`)
5. chooses hardware or software encoding based on `HardwareDetector`
6. validates and records the result

### 4. Blu-ray H.265 re-encode

The workflow step `s04_encode_bluray.py` uses a simpler HEVC re-encode policy for high-bitrate Blu-ray or remux-like inputs.

### 5. Source-resolution H.265 transcode

`transcode_to_h265()` in `transcoder.py` is designed for BR rip style conversion where you want to:

1. keep source resolution unchanged
2. transcode only video to H.265
3. copy all non-video streams (`-c:a copy -c:s copy -c:d copy -c:t copy`)
4. preserve metadata and chapters (`-map_metadata 0 -map_chapters 0`)
5. use hardware encoding when available with software fallback support

Batch operation is exposed by `batch_transcode_to_h265()` and preserves directory structure when an output root is provided.

---

## Data Models and Result Semantics

The module uses explicit status/result types rather than raw booleans.

| Type | Meaning |
|---|---|
| `ConversionResult` | one remux attempt |
| `MergeResult` | one dual-audio merge attempt |
| `UpscaleResult` | one upscale/re-encode attempt |
| `TranscodeResult` | one source-resolution H.265 transcode attempt |
| `BatchConversionSummary`, `BatchUpscaleSummary` | aggregated batch views |
| `BatchTranscodeSummary` | aggregated BR rip transcode view |
| `HardwareCapabilities` | detected encoder support and selected fallback |

This makes the video layer easy to consume from both CLI commands and workflow steps.

---

## External Dependencies

- **`ffmpeg`** for remuxing, muxing, scaling, encoding, filtering
- **`ffprobe`** for codec, bitrate, resolution, and stream inspection
- optional **hardware encoders**: NVENC, AMF, QSV

The video layer never shells out directly from the CLI. All tool execution is funneled through wrappers in `src/utils`.

---

## Safety and Recovery

Mutation-heavy operations integrate with the backup system where feasible.

- remux and merge create a `BackupEntry` before modifying output state
- successful outputs are validated and the backup is cleaned up
- failed or invalid outputs can trigger rollback
- partial outputs are explicitly deleted on failure

This is why the video layer is safe to use in batch workflows with repeat runs.

---

## Performance Characteristics

### Why profile-based encoding?

Profile definitions in `upscale_profiles.py` separate **policy** from **execution**. Examples include:

- `dvd` for balanced default runs
- `dvd-hq` for higher quality output
- `dvd-fast` for larger queues
- `jellyfin` for playback-friendly settings
- `archive` for maximum-quality preservation

### Why opportunistic hardware acceleration?

The code first checks whether a hardware encoder is listed in `ffmpeg -encoders`, then performs a tiny probe encode. This avoids trusting a codec merely because it is present in the build.

If probing fails, the system falls back to `libx265`.

---

## Integration Points

The video domain is used heavily by:

- `convert`, `merge`, and `upscale` CLI commands
- `workflow` steps `s01` through `s04`
- subtitle and trailer helpers in adjacent video flows
- statistics events for conversion, merge, and upscale completion

---

## Implementation Notes

A few decisions are intentionally heuristic:

- anime detection is filename-based
- crop plausibility is conservative to avoid accidental content loss
- Blu-ray candidacy uses a mix of filename hints, bitrate, and codec checks

Those heuristics are part of the current implementation and should be treated as adjustable policy rather than protocol guarantees.
