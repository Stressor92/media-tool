# Audio Module

## Responsibilities

The audio domain covers **music-library oriented processing**:

- recursive scanning and metadata extraction
- metadata identification and tag writing
- format conversion and enhancement
- organization helpers shared with audiobook-adjacent flows

The design separates **read-heavy discovery** from **write-heavy mutation**, which allows safe batch operation without mixing UI concerns into the core logic.

---

## Key Components

| File | Role |
|---|---|
| `library_scanner.py` | recursive discovery and parallel extraction of audio metadata |
| `metadata_extractor.py` | technical and tag-level inspection per file |
| `audio_tagger.py` | identify candidate track metadata and write tags |
| `conversion.py` | codec/container conversion workflows |
| `enhancement.py` | loudness, cleanup, and ffmpeg-based enhancement filters |
| `organization.py` | filesystem organization of audio collections |
| `workflow.py` | higher-level orchestration across audio operations |

---

## Scan Path vs Mutation Path

### Read-heavy path

`LibraryScanner.scan()` is optimized for throughput:

- discovers files by supported extension
- uses a `ThreadPoolExecutor` for per-file metadata extraction
- converts extractor failures into result objects instead of aborting the whole scan

This is appropriate for large libraries where one broken file should not block inventory generation.

### Write-heavy path

Conversion, enhancement, and tagging are intentionally more conservative:

- explicit per-file success/failure results
- predictable ffmpeg invocation through wrappers
- optional statistics emission on success
- safer defaults for batch runs

---

## Metadata and Tagging Flow

The tagging path combines provider-backed identification with local metadata writes.

High-level sequence:

1. inspect the file and existing tags
2. search providers for likely matches
3. apply a confidence threshold before writing
4. write normalized metadata through mutagen-backed helpers
5. emit `EventType.AUDIO_TAGGED` on success

This design reduces accidental tag pollution in ambiguous cases.

### Trade-off

A conservative threshold means some valid matches may be skipped, but the system avoids silently writing low-confidence metadata into a curated library.

---

## Enhancement and Conversion

The audio processing layer builds ffmpeg filter chains dynamically depending on the requested operation.

Common transformations include:

- silence trimming
- loudness normalization
- optional cleanup or EQ-like filters
- codec/container conversion

When filters are active, the path becomes a **re-encode**. When no transformation is necessary, simpler copy-like behavior can be used.

---

## External Dependencies

- **ffmpeg / ffprobe** for signal analysis and transformations
- **mutagen** for tag read/write support
- **AcoustID / MusicBrainz** integration in the identification flow
- optional utility helpers such as Chromaprint wrappers in the broader audio toolchain

---

## Operational Characteristics

| Characteristic | Current behavior |
|---|---|
| Parallelism | used for metadata extraction and scanning |
| Batch safety | one broken file does not abort a full scan |
| Result modeling | failures represented per item rather than as global exceptions |
| Telemetry | successful operations can record audio-related statistics events |

---

## Integration Points

The audio module is consumed by:

- the `audio` CLI command group
- audiobook-adjacent processing where tagging/organization logic overlaps
- statistics aggregation for conversion, normalization, and tagging events

Where exact provider behavior varies by backend or available credentials, the result should be treated as **implementation-dependent** rather than guaranteed.
