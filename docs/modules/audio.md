# Audio Module

## Scope

The audio domain provides conversion, metadata extraction/tagging, enhancement, and recursive library scanning.

## Main Components

- `conversion`: format/codec transformation
- `metadata` and extractors: read technical and tag information
- `audio_tagger`: metadata identification and write-back orchestration
- `enhancement`: silence removal, normalization, and quality filter chains
- `library_scanner`: parallel recursive scan over supported extensions

## Core Design

Audio logic is split between:

- Read-oriented operations (metadata extraction/scanning)
- Write-oriented operations (convert, tag, enhance)

Read operations prioritize throughput and parallelism. Write operations prioritize deterministic output and explicit success/failure reporting.

## Metadata Tagging Flow

`AudioTagger` orchestrates provider-based identification and mutagen-based metadata write.

High-level behavior:

1. Query provider for candidate matches.
2. Select best match subject to confidence threshold.
3. Write tags only when confidence is sufficient.
4. Record statistics event on success.

Trade-off:

- Prevents low-confidence tag pollution
- May skip valid but uncertain matches

## Enhancement Pipeline Notes

Enhancement functions construct ffmpeg audio filter chains dynamically.

Common operations:

- Silence trimming via `silenceremove`
- Loudness normalization via `loudnorm`
- Optional cleanup/equalization filters

The module uses re-encode paths when filters are active; pure copy paths are used where no filtering is required.

## Concurrency Model

`LibraryScanner` parallelizes metadata extraction via `ThreadPoolExecutor`.

Design choice:

- Failures for individual files do not abort full scan
- Per-file error details are represented in result metadata

## Integration Points

- Consumed by CLI audio commands and audiobook support flows
- Uses statistics collector for selected success events
- Uses ffmpeg wrapper for transformations
