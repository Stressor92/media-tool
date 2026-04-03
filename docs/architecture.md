# Media Tool Architecture

## Purpose and Scope

Media Tool is a CLI-driven media processing system that combines format conversion, enrichment, auditing, and library organization for multiple domains:

- Video
- Audio and audiobooks
- Subtitles and translation
- Ebooks
- Downloads
- Jellyfin metadata operations

The architecture favors a layered design where command entry points stay thin and most behavior lives in domain services.

## Layered Structure

### CLI Layer (`src/cli`)

Responsibilities:

- Parse command-line arguments and options
- Build concrete service objects
- Trigger domain workflows
- Render progress and human-readable output

Characteristics:

- Typer command groups per domain
- Minimal business logic
- Transforms user flags to strongly typed parameters used by core services

### Core Domain Layer (`src/core`)

Responsibilities:

- Domain orchestration and rules
- Pipeline composition
- Operation-specific result models
- Provider abstractions

Patterns:

- Service classes for orchestration (for example workflow runner, ebook processor)
- Dataclasses and typed dicts for operation outputs
- Protocol/provider interfaces for external integrations

### Infrastructure Utilities (`src/utils`)

Responsibilities:

- Subprocess wrappers (ffmpeg, ffprobe, yt-dlp)
- Configuration loading and override merging
- Logging setup
- File/name helper utilities

Characteristics:

- Explicit wrappers around external binaries
- Mostly stateless helper modules
- Shared by several domains

### Cross-Cutting Layers

#### Statistics (`src/statistics`)

Collects event-level operational telemetry and persists aggregates with atomic write behavior.

#### Backup and Rollback (`src/backup`)

Creates backups before destructive operations, validates post-state, and can rollback on failure.

## Control Flow Model

Typical command flow:

1. CLI command resolves config and options.
2. CLI creates or wires domain service(s).
3. Core service executes steps and calls utility wrappers.
4. Cross-cutting systems record statistics and/or create backup checkpoints.
5. Results are surfaced to CLI for progress/status rendering.

## Workflow Engine Architecture

The workflow subsystem (`src/core/workflow`) runs staged processing with explicit step contracts:

- `should_run(context)`: cheap precondition check
- `run(context)`: perform the operation
- `post_check(context, result)`: optional output verification

The runner executes numbered steps in sequence (merge/remux, upscale/re-encode, subtitles, organization), and each step updates a shared context object.

This gives the project a stable orchestration skeleton while keeping step internals isolated.

## Data and Result Modeling

The codebase uses typed result objects rather than implicit status values:

- Dataclasses for rich outcomes and metadata
- Typed dicts where lightweight serialization-friendly output is needed
- Enumerations for event and status categories

Benefits:

- Easier CLI rendering and report generation
- Less ambiguity around partial success states
- Better testability of domain decisions

## Dependency Direction

The intended dependency direction is mostly one-way:

- CLI -> Core -> Utils
- Core -> Statistics and Backup
- Statistics/Backup do not depend on CLI

Some modules still import shared helpers via absolute package paths while others use relative imports. This is implementation-dependent but functionally aligned with the same runtime boundaries.

## Error Handling and Recovery Strategy

Common strategies across domains:

- Return structured failure result instead of raising for expected operational failures
- Raise exceptions for invalid inputs or unrecoverable programming/runtime errors
- Use backup checkpoints around mutation-heavy operations
- Validate post-conditions and rollback where feasible

## Concurrency and Throughput

Concurrency is used selectively:

- Audio library scanning parallelizes metadata extraction via thread pool
- Most mutation pipelines remain sequential to preserve deterministic side effects and ordering

Trade-off:

- Improves throughput for read-heavy extraction
- Avoids difficult rollback and ordering issues in write-heavy stages

## External Tool Integration

Major integrations are shell-based wrappers:

- FFmpeg/FFprobe for media transformation and inspection
- yt-dlp for download/search workflows
- Jellyfin API operations through dedicated client/manager abstractions

Wrappers normalize process execution and return typed results to keep core modules independent of raw subprocess details.

## Known Implementation-Dependent Areas

Some behavior is intentionally best-effort or heuristic-driven:

- Provider ranking/matching quality for metadata and subtitles
- File naming extraction/parsing heuristics
- Hardware encoder availability and profile choice
- Subtitle acquisition fallback details when providers fail

Documentation in this folder marks such areas explicitly and avoids guaranteeing behavior not enforced by code contracts.


```
src/
├── cli/                      # Typer command groups (user-facing interface)
│   ├── main.py              # Root CLI dispatcher and global options
│   ├── audio_cmd.py         # Music: scan, organize, convert, improve, identify, tag, detect-language
│   ├── video_cmd.py         # Video: convert, inspect, merge, subtitle, subtitle-auto, 
│   │                         #        download-trailers, upscale, subtitle-translate, subtitle-translate-mkv
│   ├── audiobook_cmd.py     # Audiobook: scan, organize, merge
│   ├── subtitle_cmd.py      # Subtitles: download, search, translate, download-models, convert, formats
│   ├── download_cmd.py      # Download: video, music, series (yt-dlp backend)
│   ├── convert_cmd.py       # Convert: batch, single (MP4 → MKV)
│   ├── upscale_cmd.py       # Upscale: profiles, batch, single (DVD → 720p/1080p H.265)
│   ├── merge_cmd.py         # Merge: auto, manual (language variant merging)
│   ├── inspect_cmd.py       # Inspect: scan (media library CSV export)
│   ├── metadata_cmd.py      # Metadata: fetch, search (TMDB integration)
│   ├── jellyfin_cmd.py      # Jellyfin: ping, refresh, scan-status, libraries, inspect, fix-series, search
│   ├── audit_cmd.py         # Audit: run, checks (library quality analysis)
│   ├── workflow_cmd.py      # Workflow: movies (end-to-end automation pipeline)
│   ├── ebook_cmd.py         # Ebook: (startup config display), config
│   └── progress_display.py  # Rich progress reporting utilities
│
├── core/                     # Domain logic (UI-independent business rules)
│   ├── audio/               # Music processing
│   │   ├── scanner.py       # Parallel metadata extraction (tags, codec info)
│   │   ├── organizer.py     # Library organization (Artist/Album/Track structure)
│   │   ├── converter.py     # Audio format conversion (FLAC, MP3, M4A, etc.)
│   │   ├── enhancer.py      # Silence removal, normalization, quality enhancement
│   │   ├── tagger.py        # AcoustID + MusicBrainz tagging
│   │   └── models.py        # AudioFileMetadata, ConversionResult
│   │
│   ├── video/               # Video processing
│   │   ├── converter.py     # MP4 → MKV lossless remuxing
│   │   ├── merger.py        # Dual-audio merging (German + English)
│   │   ├── upscaler.py      # DVD → 720p/1080p H.265 encoding with CRF/preset profiles
│   │   ├── inspector.py     # Library scanning and CSV export (resolution, codec, duration)
│   │   ├── trailer.py       # Trailer download + MKV embedding
│   │   └── models.py        # Conversion/Upscale/Trailer results
│   │
│   ├── audiobook/           # Audiobook-specific processing
│   │   ├── scanner.py       # Audiobook library scanning
│   │   ├── organizer.py     # Folder reorganization
│   │   ├── merger.py        # Chapter file merging
│   │   └── models.py        # AudiobookMetadata
│   │
│   ├── subtitles/           # Subtitle acquisition
│   │   ├── opensubtitles_provider.py # OpenSubtitles.org API client
│   │   ├── subtitle_provider.py     # Provider abstraction
│   │   ├── subtitle_downloader.py   # Download + MKV embedding orchestration
│   │   └── models.py               # SubtitleMatch, DownloadResult
│   │
│   ├── translation/         # Offline subtitle conversion + translation
│   │   ├── converter.py     # Format conversion dispatcher
│   │   ├── format_registry.py # Format detection + lazy loading
│   │   ├── style_mapper.py  # ASS ↔ HTML tag mapping
│   │   ├── translator/      # OPUS-MT (GPU) + Argos (CPU) backends
│   │   ├── formats/         # SRT, VTT, ASS, TTML, SCC, STL, LRC, SBV readers/writers
│   │   └── models.py        # SubtitleSegment, StyleTag
│   │
│   ├── metadata/            # TMDB movie metadata scraping
│   │   ├── tmdb_client.py   # HTTP wrapper with retry/cache
│   │   ├── tmdb_provider.py # Search + detailed metadata mapping
│   │   ├── title_parser.py  # Title/year extraction from filenames
│   │   ├── match_selector.py # Auto/interactive selection
│   │   ├── nfo_writer.py    # Jellyfin/Kodi-compatible .nfo generation
│   │   ├── artwork_downloader.py # Parallel poster/fanart/banner downloading
│   │   ├── metadata_pipeline.py  # Orchestration
│   │   └── models.py        # MovieMetadata, ArtworkType, PipelineResult
│   │
│   ├── jellyfin/            # Jellyfin REST API integration
│   │   ├── client.py        # HTTP client with retries + structured exceptions
│   │   ├── library_manager.py # Refresh, scan status, item lookup
│   │   ├── metadata_inspector.py # Missing/wrong metadata detection
│   │   ├── metadata_fixer.py # Auto-repair (refresh trigger for fixable issues)
│   │   └── auto_trigger.py  # Workflow hook → library refresh
│   │
│   ├── download/            # yt-dlp media downloading
│   │   ├── download_manager.py # Request orchestration + retry
│   │   ├── format_selector.py # Video/audio/subtitle format selection
│   │   ├── yt_dlp_runner.py # Process wrapper + cookie handling
│   │   └── models.py        # DownloadRequest, DownloadResult, DownloadStatus
│   │
│   ├── ebook/               # E-book processing (identification, metadata, covers, normalization)
│   │   ├── models.py        # BookIdentity, BookMetadata
│   │   ├── identification/  # ISBN extraction, filename parsing, confidence scoring
│   │   │   ├── isbn_extractor.py    # Pattern matching + ISBN13 normalization
│   │   │   ├── book_identifier.py   # Multi-strategy (ISBN, metadata, filename)
│   │   │   └── confidence_scorer.py # Match scoring
│   │   ├── metadata/        # Metadata retrieval from providers
│   │   │   ├── metadata_service.py     # Provider orchestration + fuzzy matching
│   │   │   └── providers/              # OpenLibrary, Google Books API integrations
│   │   ├── cover/           # Cover image acquisition + embedding
│   │   │   ├── cover_service.py       # Fetch + embed orchestration
│   │   │   ├── cover_selector.py      # Resolution/aspect-ratio based ranking
│   │   │   └── providers/             # OpenLibrary, Google Books cover APIs
│   │   └── normalization/   # EPUB metadata embedding, cover insertion, TOC generation
│   │       ├── metadata_embedder.py # OPF field updates
│   │       ├── epub_validator.py    # Archive + metadata validation
│   │       ├── toc_generator.py     # Navigation document generation
│   │       └── normalizer.py        # Full workflow orchestration
│   │
│   ├── audit/               # Library quality auditing
│   │   ├── auditor.py       # Orchestration engine
│   │   ├── check_registry.py # Check discovery (A01–Z99 IDs)
│   │   ├── reporter.py      # Terminal + CSV/JSON output
│   │   └── models.py        # Check, Finding, AuditReport
│   │
│   ├── workflow/            # Automation pipeline orchestration
│   │   ├── runner.py        # Movie pipeline builder + executor (merge → convert → upscale → subtitle → organize)
│   │   └── models.py        # WorkflowContext, StepResult
│   │
│   ├── language_detection/  # Audio language identification (heuristic + Whisper)
│   │   ├── detector.py      # Multi-strategy detection
│   │   └── models.py        # DetectionResult
│   │
│   ├── naming/              # Jellyfin-compatible file path generation
│   │   └── namer.py         # Naming template engine
│   │
│   └── __init__.py
│
├── utils/                    # Shared utilities and low-level wrappers
│   ├── config.py            # TOML loader + environment overrides (API keys, tool paths, defaults)
│   ├── logging_config.py    # Rich console + rotating file logging setup
│   ├── ffmpeg_runner.py     # FFmpeg subprocess wrapper (container conversion, codec re-encoding)
│   ├── ffprobe_runner.py    # FFprobe JSON wrapper (media inspection, metadata extraction)
│   ├── ytdlp_runner.py      # yt-dlp subprocess wrapper (format selection, cookies)
│   ├── video_hasher.py      # Opensubtitles.org-compatible video file hashing
│   ├── url_validator.py     # URL validation + platform classification (YouTube, Soundcloud, etc.)
│   ├── audio_analyzer.py    # Audio metadata extraction using ffprobe
│   ├── audio_processor.py   # Audio manipulation utilities (ffmpeg-based)
│   ├── epub_reader.py       # EPUB container reading and metadata extraction (OPF parsing)
│   ├── epub_writer.py       # EPUB metadata updates, cover embedding, navigation generation
│   ├── pdf_reader.py        # PDF metadata and text extraction (optional pypdf dependency)
│   ├── image_processor.py   # Image resizing + quality optimization (Pillow)
│   ├── fuzzy_matcher.py     # String similarity scoring (difflib)
│   ├── ffprobe_cache.py     # Parallel ffprobe caching for batch operations
│   └── __init__.py
│
├── gui/                      # (Future) Graphical user interface (PySide6/Qt)
│
└── obsolet_ps_scrips/        # Legacy PowerShell scripts (deprecated, replaced by Python)

tests/
├── unit/                     # Unit tests for isolated functions and classes
├── integration/              # Integration tests for full workflows
├── fixtures/                 # Test data and helper functions
├── conftest.py              # Pytest configuration and shared fixtures
├── ebook_test_support.py    # E-book test helpers (EPUB creation, image generation)
└── cleanup_test_artifacts.py # Test artifact cleanup
```