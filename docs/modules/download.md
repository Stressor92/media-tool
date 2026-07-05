# Download Module

## Responsibilities

The download domain orchestrates **remote media retrieval** using yt-dlp and converts provider-specific failure modes into user-meaningful result objects.

It supports:

- single URL downloads
- playlist/series-style downloads
- dry-run inspection
- cookie-aware retry logic for restricted providers
- normalization of authentication, geo-blocking, and rate-limit errors

---

## Core Components

| File | Role |
|---|---|
| `download_manager.py` | high-level orchestration and retry policy |
| `models.py` | immutable request/result models such as `DownloadRequest` and `DownloadResult` |
| `format_selector.py` | build yt-dlp format strings and post-processor configuration |
| `yt_dlp_runner.py` | low-level runner and info parsing |
| `post_processor.py` | post-download adjustments where needed |

---

## `DownloadManager` Flow

`DownloadManager.download(request)` performs one complete download cycle:

1. log the requested URL and media type
2. short-circuit for `dry_run`
3. extract remote info without downloading where needed
4. enrich the request using the extracted metadata
5. perform the actual download, optionally retrying with browser cookies
6. resolve an output path and return a typed `DownloadResult`

### Playlist-tolerant behavior

The manager intentionally switches into a playlist-friendly mode when:

- `request.media_type == MediaType.SERIES`, or
- the URL looks like a playlist/album/set (`list=`, `/sets/`, `/playlist`, `/album/`)

In that mode it requests flattened metadata and logs per-item progress instead of assuming a single-track response.

---

## Error Normalization Strategy

One of the most important responsibilities in this module is **turning raw yt-dlp/provider failures into actionable messages**.

The manager explicitly classifies errors such as:

- authentication/login requirements
- stale browser cookies
- missing PO token cases for harder YouTube scenarios
- provider rate limiting
- geo restrictions
- general availability failures (`private video`, `unsupported URL`, etc.)

This keeps the CLI behavior predictable even though the upstream providers are volatile.

---

## Cookie and Retry Policy

If an authentication error occurs and the caller did not already provide cookies, the manager may retry using browser cookies from:

1. `chrome`
2. `firefox`

This is intentionally limited and conservative. The system stops automatic retries when it detects rate-limiting or a non-auth-related failure.

---

## Result Modeling

The download layer uses frozen request models and structured results so later stages can safely consume them.

| Type | Purpose |
|---|---|
| `DownloadRequest` | captures desired URL, media type, output directory, subtitle/language preferences, cookies, yt-dlp extras |
| `TrackInfo` | normalized metadata extracted from yt-dlp info |
| `DownloadResult` | reports `SUCCESS`, `FAILED`, or `SKIPPED` plus output path or error message |

---

## External Dependencies

- **yt-dlp** for extraction and downloading
- remote providers such as YouTube and SoundCloud through yt-dlp extractors
- browser-cookie or Netscape cookie-file workflows for restricted content

The module itself does not hardcode provider-specific scraping logic; it relies on yt-dlp and then adds policy around it.

---

## Integration Points

The download module is primarily used by the `download` CLI command group, but its outputs are also suitable as inputs to later local processing such as conversion or workflow-based organization.

Because remote failure is expected, the module treats many failures as **operational outcomes** rather than programmer errors.

---

## Output Templates

For `MediaType.SERIES`, the output template depends on mode:

- video-oriented series mode: `Series/Season XX/<playlist_index> - <title>.<ext>`
- audio-oriented series mode (`extract_audio=True`, e.g. `--format mp3`): `Author/Album/Song.<ext>`

This keeps playlist-as-music downloads compatible with music-library folder conventions.
