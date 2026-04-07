# Internal: FFmpeg Integration

## Scope

FFmpeg and FFprobe are the most important external tools in the repository. Their integration is deliberately centralized in low-level wrappers under `src/utils`.

This document describes how those wrappers are used and why the design matters.

---

## Core Wrappers

| File | Responsibility |
|---|---|
| `utils/ffmpeg_runner.py` | execute ffmpeg commands and return structured results |
| `utils/ffprobe_runner.py` | run ffprobe and parse JSON stream/format data |
| `utils/ffprobe_cache.py` | cache and parallelize probe work for audit/scan paths |

### `run_ffmpeg(args)`

This function prepends the configured ffmpeg binary, executes the command, captures stdout/stderr as **bytes**, and returns an `FFmpegResult` with:

- `success`
- `return_code`
- full command list
- raw stdout/stderr payloads

The byte-oriented capture is intentional: it avoids text-decoding problems during process execution and decodes only for presentation/logging.

### `probe_file(path)`

This function runs ffprobe with JSON output and returns a `ProbeResult` with convenience accessors such as:

- `video_streams()`
- `audio_streams()`
- `subtitle_streams()`
- `first_video()`

### `probe_cropdetect(path, ...)`

This is a specialized helper that runs ffmpeg’s cropdetect filter on a short sample and extracts the last detected crop expression.

---

## Architectural Rule: no business logic in wrappers

A key design choice in the codebase is that wrappers should **not** decide domain policy.

For example:

- `ffmpeg_runner.py` does not decide when to upscale or how to name outputs
- `ffprobe_runner.py` does not decide whether a file counts as a DVD rip

Those decisions belong in `core.video`, `core.audio`, `core.audit`, and other domain modules.

This separation makes the wrappers reusable and far easier to test.

---

## How higher layers use the wrappers

Typical domain flow:

1. core service decides what operation should happen
2. it builds an explicit ffmpeg argument list
3. the wrapper executes the process and returns a typed result
4. the core service interprets success/failure and applies backup/statistics logic

This pattern is used repeatedly in:

- video remuxing and merging
- DVD upscaling and HEVC re-encoding
- subtitle muxing
- audio enhancement/conversion
- audit and inspection probes

---

## Safety and Diagnostics

The integration code is designed to make failures diagnosable:

- stderr is always captured
- return codes are never silently ignored
- warnings include command metadata and stderr tails for troubleshooting
- `FileNotFoundError` is raised clearly when `ffmpeg` or `ffprobe` is not available

This matters because external tool failures are common in media workflows and need to be distinguished from application logic bugs.

---

## Performance Notes

The project uses FFmpeg/FFprobe in a few distinct modes:

- **cheap probe calls** for metadata inspection and eligibility checks
- **long-running transforms** for remuxing, upscaling, and muxing
- **sample-based probes** such as crop detection

Keeping those responsibilities in small wrappers makes it easier to optimize or cache them later without changing every domain module.