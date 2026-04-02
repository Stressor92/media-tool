# media-tool

media-tool is a modular Python CLI for preparing video, audio, subtitles, metadata, downloads, audiobooks, and ebooks for Jellyfin or NAS libraries.

Status: alpha, active development.

## What It Does

- Convert and remux media files with ffmpeg/ffprobe wrappers.
- Upscale DVD-quality video with profile-based H.265 workflows.
- Merge language variants into dual-audio outputs.
- Download and manage subtitles (OpenSubtitles + local workflows).
- Translate subtitle files offline.
- Fetch movie metadata and artwork from TMDB.
- Download web media (video/music/series) with yt-dlp.
- Audit media libraries for quality and naming issues.
- Run end-to-end automation workflows.
- Process ebooks (metadata, covers, normalization helpers, and config-aware CLI entry).

## Installation

Prerequisites:

- Python 3.11+
- ffmpeg and ffprobe available on PATH
- git

```bash
git clone https://github.com/yourusername/media-tool.git
cd media-tool
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
pip install -e .
```

Verify:

```bash
media-tool --help
```

## Configuration

Create local config from template:

```bash
copy media-tool.example.toml media-tool.toml
```

Important sections:

- `[api]`: API keys (OpenSubtitles, AcoustID, TMDB).
- `[tools]`: binary names/paths (`ffmpeg`, `ffprobe`, `yt_dlp`).
- `[download]`: default output paths and yt-dlp defaults.
- `[ebook]`: ebook defaults (format, cover download, provider order).
- `[ebook.organization]`: output folder structure template.
- `[ebook.conversion]`: conversion target format.
- `[workflow.movies]`: movie workflow behavior.
- `[jellyfin]`: Jellyfin base URL and API key.

Environment overrides are supported:

- `MEDIA_TOOL_CONFIG` for alternate config path.
- Nested overrides like `MEDIA_TOOL_API__TMDB_API_KEY`.
- Legacy compatibility vars (`TMDB_API_KEY`, `OPENSUBTITLES_API_KEY`, `FFMPEG_BIN`, `FFPROBE_BIN`) still work.

## Logging

Global flags on all commands:

- `--verbose` / `-v`: INFO logging
- `--debug`: DEBUG logging
- `--quiet` / `-q`: warnings/errors only
- `--log-file PATH`: rotating file logs
- `--log-json`: JSON logs (when `--log-file` is set)

## CLI Overview

media-tool provides 14 command groups for managing your media library. Most support recursive batch operations, parallel processing, and graceful error handling for large-scale NAS automation.

### convert — Container remuxing (MP4 → MKV)

Remux media files losslessly without re-encoding. Useful for standardizing container formats.

- `media-tool convert single input.mp4` — Convert one file
- `media-tool convert batch "C:\Videos" --recursive` — Batch convert all MP4s, preserving directory structure
- `media-tool convert batch "E:\Movies" --dry-run` — Preview what would be converted

**Common workflow:**
```bash
# Standardize your video library to MKV
media-tool convert batch "E:\Movies" --recursive --video h264,h265 --audio aac,ac3,dts
# Then verify quality with inspect
media-tool inspect scan "E:\Movies" --output report.csv
```

### upscale — H.265 video re-encoding (DVD → 720p/1080p)

Upscale lower-quality video using profile-based encoding presets. Optimized for DVD sources.

- `media-tool upscale profiles` — List available CRF + preset profiles (dvd-fast, dvd-balanced, dvd-hq)
- `media-tool upscale single input.mp4 --profile dvd-balanced` — Upscale one file
- `media-tool upscale batch "E:\DVDs" --recursive --profile dvd-hq` — Batch upscale with high quality (slower)
- `media-tool upscale batch "E:\DVDs" --recursive --profile dvd-fast -q` — Quiet mode, fast profile (good preview quality)

**Common workflow:**
```bash
# Upscale your DVD collection to 1080p H.265 (high quality, but slow)
media-tool --verbose upscale batch "E:\DVDs" --recursive --profile dvd-hq --workers 2
# Monitor progress and resource usage. Can pause/resume in-progress batches.
```

### inspect — Library scanning & CSV export

Scan a media library and generate reports on resolution, codec, duration, file size.

- `media-tool inspect scan "E:\Movies"` — Show summary stats
- `media-tool inspect scan "E:\Movies" --output movies.csv` — Export detailed CSV
- `media-tool inspect scan "E:\Movies" --recursive --format mkv,mp4` — Filter by extension

**Common workflow:**
```bash
# Audit your Jellyfin library before automation
media-tool inspect scan "Y:\Jellyfin\Movies" --recursive --output before_audit.csv
# Make improvements...
media-tool inspect scan "Y:\Jellyfin\Movies" --recursive --output after_audit.csv
# Compare the CSVs to verify changes
```

### merge — Dual-audio merging (German + English)

Merge multiple audio tracks (typically German + English) into a single file with all tracks preserved.

- `media-tool merge auto "C:\Movies" --recursive` — Auto-detect + merge German/English pairs
- `media-tool merge manual "movie_german.mkv" "movie_english.mkv" --output movie_merged.mkv` — Merge specific files

**Use case:** You downloaded a German movie and English audio separately; merge them into one MKV with selectable audio tracks.

### audio — Music library processing

Scan, organize, tag, convert, and enhance audio files.

- `media-tool audio scan "M:\Music"` — Discover metadata
- `media-tool audio organize "M:\Music" --output "M:\Music_Organized" --structure "{artist}/{album}/{title}"` — Reorganize by metadata
- `media-tool audio convert "M:\Music" --recursive --format mp3 --bitrate 320k` — Convert FLAC to MP3
- `media-tool audio improve "song.flac"` — Remove silence, normalize loudness
- `media-tool audio auto-tag "M:\Music" --recursive` — Tag with AcoustID + MusicBrainz
- `media-tool audio detect-language "song.mp3"` — Identify language (heuristic or Whisper)

**Common workflow:**
```bash
# Process your music library end-to-end
media-tool --verbose audio scan "M:\Music"
media-tool audio auto-tag "M:\Music" --recursive
media-tool audio organize "M:\Music" --output "M:\Music_Tagged" --structure "{artist}/{album}/{track_number} - {title}"
media-tool audio convert "M:\Music_Tagged" --recursive --format mp3 --bitrate 320k --output "M:\Music_MP3"
```

### video — Video-specific operations

Convert, inspect, merge, add/translate subtitles, download trailers, upscale.

- `media-tool video convert "movie.mp4"` — Remux to MKV
- `media-tool video inspect "E:\Movies"` — Scan for codecs and resolution
- `media-tool video merge "german.mkv" "english.mkv"` — Merge language variants
- `media-tool video subtitle "movie.mkv" "subs.srt" --language en` — Embed subtitle track
- `media-tool video subtitle-auto "E:\Movies" --recursive --languages en,de` — Auto-download and embed missing subtitles
- `media-tool video download-trailers "movie.mkv"` — Fetch trailer from TMDB and embed
- `media-tool video upscale "dvd.mp4" --profile dvd-balanced` — Upscale to 720p/1080p
- `media-tool video subtitle-translate "movie.mkv" --from de --to en` — Translate existing subtitles
- `media-tool video subtitle-translate-mkv "movie.mkv" --language de --target-language en` — Translate in-place

**Common end-to-end workflow:**
```bash
# Full movie preparation
media-tool metadata fetch "Y:\Raw_Movies\movie.mkv"  # Fetch TMDB metadata
media-tool video subtitle-auto "Y:\Raw_Movies" --recursive --languages en,de
media-tool video upscale "Y:\Raw_Movies\dvd_movie.mkv" --profile dvd-hq --output "Y:\Jellyfin\Movies"
media-tool jellyfin refresh "Y:\Jellyfin\Movies"  # Refresh Jellyfin library
```

### audiobook — Audiobook organization

Scan, organize, and merge audiobook chapter files.

- `media-tool audiobook scan "M:\Audiobooks"` — Discover audiobook metadata
- `media-tool audiobook organize "M:\Audiobooks" --output "M:\Audiobooks_Org" --structure "{author}/{series}/{title}"` — Reorganize
- `media-tool audiobook merge "book_chapters/" --output "book_merged.m4b"` — Merge all chapters into single file

### subtitle — Subtitle acquisition & conversion

Download subtitles, search providers, translate offline, convert formats.

- `media-tool subtitle download "movie.mkv" --languages en,de` — Download + embed subtitles
- `media-tool subtitle search "movie.mkv" --languages en` — Search OpenSubtitles (preview only)
- `media-tool subtitle translate "subtitles.srt" --from de --to en` — Translate SRT file offline (OPUS-MT or Argos)
- `media-tool subtitle download-models` — Pre-download translation models (offline operation)
- `media-tool subtitle convert "subtitles.ass" --output "subtitles.srt"` — Convert ASS/SSA/VTT/SCC/STL to SRT/VTT
- `media-tool subtitle formats` — List supported formats

**Common workflow:**
```bash
# Prepare subtitles for Jellyfin
media-tool subtitle download "movie.mkv" --languages en,de --output "movie"
# Downloads/converts to SRT in same directory as movie
# Then embed:
media-tool video subtitle "movie.mkv" "movie.srt" --language en
```

### download — Web media downloading (yt-dlp)

Download video, music, or entire series from YouTube, Soundcloud, and 1000+ sites.

- `media-tool download video "https://youtube.com/watch?v=abc123" --resolution 1080` — Download one video
- `media-tool download video "https://url..." --output "E:\Downloads" --subtitle en,de` — Download with subtitles
- `media-tool download music "https://soundcloud.com/..." --format mp3` — Download audio
- `media-tool download series "https://youtube.com/playlist?list=..." --recursive` — Download entire playlist

**Use case:** Download a movie, music video, or educational series before processing with other commands.

### workflow — Automation pipelines

Run end-to-end processing workflows combining merge → convert → upscale → subtitle → organize.

- `media-tool workflow movies "E:\RawMovies" --output "E:\Jellyfin\Movies"` — Full movie workflow

**What it does:**
1. Scan input folder for video files
2. Auto-merge language variants (if found)
3. Remux to MKV (normalize container)
4. Upscale if DVD-quality (based on config)
5. Download + embed subtitles
6. Organize to output structure
7. Generate Jellyfin metadata (.nfo files + artwork)

```bash
# Complete automation
media-tool --verbose workflow movies "E:\Raw_Movies" --output "Y:\Jellyfin\Movies" --profile dvd-hq
# Followed by:
media-tool jellyfin refresh "Y:\Jellyfin\Movies"
```

### jellyfin — Jellyfin library management

Ping server, refresh libraries, inspect metadata, auto-fix issues.

- `media-tool jellyfin ping` — Test connection to Jellyfin server (from config)
- `media-tool jellyfin refresh "Y:\Jellyfin\Movies"` — Trigger library scan
- `media-tool jellyfin scan-status` — Check current scan progress
- `media-tool jellyfin libraries` — List all Jellyfin libraries
- `media-tool jellyfin inspect "Y:\Jellyfin\Movies"` — Report missing metadata
- `media-tool jellyfin fix-series "Y:\Jellyfin\Series"` — Auto-fix naming issues in series folder
- `media-tool jellyfin search "Star Wars"` — Search within Jellyfin

**Common workflow:**
```bash
# After bulk importing movies
media-tool jellyfin ping
media-tool jellyfin refresh "Y:\Jellyfin\Movies"
media-tool jellyfin scan-status  # Wait for scan to complete
media-tool jellyfin inspect "Y:\Jellyfin\Movies"  # Check for missing metadata
```

### audit — Library quality checks

Run audits on media library for naming, metadata, codec issues. Check registry covers 50+ audit rules (A01–Z99).

- `media-tool audit run "Y:\Jellyfin\Movies"` — Run all checks, print summary
- `media-tool audit run "Y:\Jellyfin\Movies" --output audit_report.json` — Export detailed JSON report
- `media-tool audit checks` — List all available audit checks (descriptions + IDs)

**Use case:** Verify library quality before sharing with users or troubleshooting Jellyfin metadata issues.

### metadata — TMDB metadata fetching

Fetch movie metadata and artwork from TMDB. Generates Jellyfin/Kodi-compatible .nfo files.

- `media-tool metadata fetch "Y:\Movies"` — Auto-match all movies, download metadata + artwork
- `media-tool metadata fetch "Y:\Movies" --interactive` — Prompt for confirmation on each match
- `media-tool metadata search "The Matrix"` — Search TMDB without processing files
- `media-tool metadata search "movie.mkv"` — Extract title from filename and search

**Common workflow:**
```bash
# Bulk update Jellyfin metadata
media-tool metadata fetch "Y:\Jellyfin\Movies" --output "Y:\Jellyfin\Movies"
# Downloads poster.jpg, fanart.jpg, movie.nfo for each file
# Jellyfin picks up .nfo files automatically on refresh
```

### ebook — E-book processing

Identify, enrich, organize, audit, deduplicate, and convert ebook libraries.

- `media-tool ebook` — Display current ebook config settings
- `media-tool ebook config` — Detailed ebook configuration (same as above)
- `media-tool ebook identify "book.epub"` — Identify title/author/ISBN and confidence
- `media-tool ebook enrich "library/" --recursive` — Identify + metadata + cover + normalization
- `media-tool ebook organize "downloads/" "library/" --dry-run` — Preview target structure
- `media-tool ebook organize "downloads/" "library/"` — Move/copy into Jellyfin-compatible layout
- `media-tool ebook audit "library/" --output "audit-report.txt"` — Library quality audit report
- `media-tool ebook deduplicate "library/" --dry-run` — Show duplicate groups and best version picks
- `media-tool ebook deduplicate "library/" --delete` — Remove non-best duplicates
- `media-tool ebook convert "book.epub" mobi --profile kindle_high` — Convert format via Calibre

**Behavior highlights:**
- Dry-run support on enrich, organize, deduplicate, and convert
- Backups before conversion
- Safe move/copy validations for organization
- Duplicate ranking by format, size, and filename quality
- Audit checks for metadata gaps, missing covers, missing ISBN, and series gaps

```toml
# From media-tool.toml
[ebook]
preferred_format = "epub"
download_cover = true
metadata_providers = ["openlibrary", "googlebooks"]

[ebook.organization]
structure = "{author}/{series}/{title}"
```

---

## Typical Workflows

### 🎬 **Movie Library Preparation** (download → metadata → organize → Jellyfin)

```bash
# 1. Download movie (e.g., from MegaBox)
media-tool download video "https://megabox.com/..."  --output "E:\Raw" --subtitle en,de

# 2. Process through full pipeline
media-tool --verbose workflow movies "E:\Raw" --output "Y:\Jellyfin\Movies" --profile dvd-hq

# 3. Refresh Jellyfin library
media-tool jellyfin ping
media-tool jellyfin refresh "Y:\Jellyfin\Movies"

# 4. Verify quality
media-tool jellyfin inspect "Y:\Jellyfin\Movies"
media-tool audit run "Y:\Jellyfin\Movies"
```

### 🎵 **Music Library Overhaul** (scan → tag → organize → convert)

```bash
# Discover + tag
media-tool audio scan "M:\Music"
media-tool audio auto-tag "M:\Music" --recursive

# Organize by metadata
media-tool audio organize "M:\Music" --output "M:\Music_Tagged" \
  --structure "{artist}/{album}/{track_number:02d} - {title}"

# Convert for portable devices (MP3 320k)
media-tool audio convert "M:\Music_Tagged" --recursive \
  --format mp3 --bitrate 320k --output "M:\Music_Portable"
```

### 🎧 **Subtitle Management** (download → translate → normalize)

```bash
# Mass download missing subtitles
media-tool subtitle download "E:\Movies" --recursive \
  --languages en,de --fallback en

# Translate German subtitles to English
media-tool subtitle translate "E:\Movies\movie.srt" \
  --from de --to en --output "movie_en.srt"

# Or translate in-place on MKV files
media-tool video subtitle-translate-mkv "E:\Movies\movie.mkv" \
  --language de --target-language en
```

### 🚀 **Large-scale Upscaling Batch** (DVD → 1080p)

```bash
# Fast preview quality (2× speedup, lower quality)
media-tool upscale batch "E:\DVDs" --recursive \
  --profile dvd-fast --workers 4 --output "E:\Upscaled_Fast"

# High quality (slower, best results)
media-tool --verbose upscale batch "E:\DVDs" --recursive \
  --profile dvd-hq --workers 2 --output "E:\Upscaled_HQ"

# Check results before committing
media-tool inspect scan "E:\Upscaled_HQ" --output report.csv
```

---

## Quick Command Reference

Single-command examples by use case (see **Typical Workflows** above for multi-step scenarios):

```bash
# Media inspection & auditing
media-tool inspect scan "E:\Movies" --output report.csv
media-tool audit run "Y:\Jellyfin\Movies" --output audit.json

# Batch operations with logging
media-tool --verbose convert batch "E:\Downloads" --recursive
media-tool --verbose upscale batch "E:\DVDs" --recursive --profile dvd-hq
media-tool subtitle download "E:\Movies" --recursive --languages en,de,fr

# Jellyfin integration
media-tool jellyfin ping
media-tool jellyfin refresh "Y:\Jellyfin\Movies"
media-tool jellyfin inspect "Y:\Jellyfin\Movies"

# Music and audio
media-tool audio auto-tag "M:\Music" --recursive
media-tool audio organize "M:\Music" --output "M:\Music_Organized" --structure "{artist}/{album}/{title}"
media-tool audio convert "M:\Music" --recursive --format mp3 --bitrate 320k --output "M:\Music_MP3"

# Subtitles and translation
media-tool subtitle download "movie.mkv" --languages en,de
media-tool subtitle translate "subs.srt" --from de --to en --output "subs_en.srt"
media-tool video subtitle-auto "E:\Movies" --recursive --languages en,de

# Download from web
media-tool download video "https://youtube.com/watch?v=abc123" --resolution 1080
media-tool download music "https://soundcloud.com/..." --format mp3
media-tool download series "https://youtube.com/playlist?list=..." --recursive

# Configuration & diagnostics
media-tool ebook config
media-tool --debug upscale single dvd.mkv  # Deep diagnostics
media-tool --quiet convert batch "E:\Videos" --recursive  # Minimal output

# Combining with logging
media-tool --verbose --log-file logs/media-tool.log workflow movies "E:\Raw" --output "Y:\Jellyfin"
media-tool --debug --log-file logs/debug.jsonl --log-json subtitle download movie.mkv
```

## Testing

Install dev dependencies (already included in `requirements.txt` in this repo setup), then run:

```bash
python -m pytest -q
```

Integration test modes:

```bash
# Offline integration tests only
python -m pytest tests/integration -m "not live_integration" -q

# Opt-in live integration tests
set MEDIA_TOOL_LIVE_INTEGRATION_TESTS=1
python -m pytest tests/integration -m live_integration -q
```

Type checking:

```bash
python -m mypy .
```

Formatting and linting:

```bash
python -m ruff format .
python -m ruff check . --fix
```

Pre-commit hooks (includes Ruff + mypy):

```bash
python -m pre_commit run --all-files
```

## Project Structure

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

### Architecture Highlights

- **Layered design**: Core logic is UI-independent; both CLI and GUI use the same backend.
- **Provider pattern**: Metadata (OpenLibrary, Google Books), covers, and subtitles are pluggable.
- **Service orchestration**: High-level services coordinate multiple providers (e.g., `MetadataService` searches multiple providers, ranks results).
- **Configuration-driven**: TOML config + environment overrides for tool paths, API keys, and behavioral defaults.
- **Structured logging**: Rich console output with optional rotating file logs (text or JSON format).
- **Batch-safe execution**: Explicit status enums prevent silent failures in large NAS automation runs.

