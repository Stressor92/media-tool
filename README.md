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
[api]
googlebooks_api_key = ""

[ebook]
preferred_format = "epub"
download_cover = true
metadata_providers = ["openlibrary", "googlebooks"]

[ebook.organization]
structure = "{author}/{series}/{title}"
```

`api.googlebooks_api_key` is optional. Leave it empty to use unauthenticated Google Books requests, or set it to increase quota and reduce lookup failures during ebook metadata enrichment.

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

Key sections:

| Section | Purpose |
| --- | --- |
| `[api]` | API keys and user-agent values (OpenSubtitles, AcoustID, TMDB, Google Books) |
| `[tools]` | Executable names/paths (`ffmpeg`, `ffprobe`, `yt_dlp`) |
| `[paths]` | Library, incoming, and temp directories |
| `[defaults.subtitles]` | Default subtitle languages/embed behavior |
| `[defaults.audio]` | Audio confidence defaults |
| `[download]` | yt-dlp output and quality defaults |
| `[upscale]` | Hardware encoder behavior and fallback settings |
| `[translation]` | Subtitle translation backend and chunking options |
| `[language_detection]` | Audio language detection behavior |
| `[metadata]` + sub-sections | Metadata and artwork defaults |
| `[ebook]` + sub-sections | Ebook format, provider, organization, conversion defaults |
| `[workflow.movies]` | Movie pipeline step behavior |
| `[jellyfin]` + sub-sections | Jellyfin endpoint and integration controls |
| `[statistics]` | Statistics enablement/history location |
| `[backup]` + sub-sections | Backup storage, cleanup policy, validation tolerances |

Environment overrides are supported by the config loader, including `MEDIA_TOOL_CONFIG` for a custom config path.

