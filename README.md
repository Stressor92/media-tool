🎬 media-tool

Tools and scripts for preparing media, movies, TV shows, music, and audiobooks for Jellyfin and NAS archiving.

Vision

This project aims to evolve from simple scripts into a modular, extensible media processing toolkit with:
CLI interface (first stage)
Automated workflows for NAS environments
Future GUI application
Integration with tools like ffmpeg, Whisper, and Jellyfin

## 🚦 CURRENT PROJECT STATUS

- in development | ALPHA

## 🧰 How to run full suite and interpret legacy failures

Run the default suite with `pytest -q`.
Offline integration tests run by default; live external-service tests are explicitly opt-in via marker/environment.

```bash
# default: unit + offline integration
python -m pytest -q

# only offline integration
python -m pytest tests/integration -m "not live_integration" -q

# opt-in live integration
set MEDIA_TOOL_LIVE_INTEGRATION_TESTS=1
python -m pytest tests/integration -m live_integration -q
```

## Architecture

The project follows a layered architecture designed for modularity, extensibility, and separation of concerns:

```
src/
├── core/              # Business logic (independent of UI/CLI)
│   ├── audio/         # Audio processing modules (conversion, enhancement, metadata)
│   ├── video/         # Video processing modules (conversion, upscaling, merging)
│   ├── audiobook/     # Audiobook-specific logic (organization, chapter merging)
│   ├── subtitles/     # Subtitle provider abstraction + OpenSubtitles workflow
│   ├── translation/   # Subtitle format converter + offline translation (OPUS-MT)
│   │   ├── formats/   # Per-format readers/writers (SRT, VTT, ASS, TTML, SCC, STL, LRC, SBV)
│   │   ├── format_registry.py  # Lazy dispatcher + magic-byte detection
│   │   ├── style_mapper.py     # ASS↔HTML tag conversion
│   │   └── converter.py        # SubtitleConverter public API
│   ├── metadata/      # TMDB metadata + artwork pipeline
│   │   ├── models.py           # MovieMetadata, ArtworkType, PipelineResult
│   │   ├── tmdb_client.py      # HTTP client with retry/cache/fallback language
│   │   ├── tmdb_provider.py    # Search + detailed metadata mapping
│   │   ├── title_parser.py     # Parse title/year from file or folder name
│   │   ├── match_selector.py   # Auto or interactive match selection
│   │   ├── nfo_writer.py       # Jellyfin/Kodi compatible movie NFO writer
│   │   ├── artwork_downloader.py # Parallel artwork download
│   │   └── metadata_pipeline.py # End-to-end orchestration
│   ├── jellyfin/      # Jellyfin REST API integration
│   │   ├── client.py           # HTTP client with retry + structured exceptions
│   │   ├── library_manager.py  # Refresh, scan status, item lookup
│   │   ├── metadata_inspector.py # Detect missing/wrong metadata
│   │   ├── metadata_fixer.py   # Auto-repair fixable issues
│   │   └── auto_trigger.py     # Pipeline hook → automatic library refresh
│   ├── download/      # yt-dlp domain (request models, runner, selector, manager)
│   └── naming/        # File naming utilities for Jellyfin compatibility
├── cli/               # Command-line interface (Typer-based)
│   ├── main.py        # Main CLI entry point and command dispatcher
│   ├── audio_cmd.py   # Audio/music processing commands
│   ├── audiobook_cmd.py # Audiobook processing commands
│   ├── convert_cmd.py # MP4 → MKV conversion
│   ├── inspect_cmd.py # Media library inspection
│   ├── merge_cmd.py   # Video merging with multiple audio tracks
│   ├── subtitle_cmd.py # Subtitle search/download commands
│   ├── download_cmd.py # yt-dlp download commands (video/music/series)
│   ├── upscale_cmd.py # Video upscaling
│   ├── video_cmd.py   # General video processing commands
│   ├── jellyfin_cmd.py # Jellyfin library management commands
│   └── metadata_cmd.py # TMDB metadata and artwork commands
├── utils/             # Shared helpers and low-level utilities
│   ├── audio_analyzer.py       # Audio metadata extraction using ffprobe
│   ├── audio_processor.py      # Audio manipulation and enhancement tools
│   ├── config.py               # TOML + env configuration loader
│   ├── ffmpeg_runner.py        # FFmpeg wrapper for media processing
│   ├── ffprobe_runner.py       # FFprobe wrapper for media analysis
│   ├── url_validator.py        # URL validation + platform classification
│   └── whisper_models/         # Whisper model storage (optional, future)
├── gui/               # (future) Graphical user interface (PySide6/Qt) #TODO
│
tests/                 # Comprehensive test suite
├── unit/              # Unit tests for core modules
├── integration/       # Integration tests for CLI workflows
└── conftest.py        # Pytest fixtures and configuration
│
obsolet_ps_scrips/     # Legacy PowerShell scripts (deprecated, replaced by Python)
```

### Download Layering (yt-dlp)

```
CLI (src/cli/download_cmd.py)
	-> DownloadManager (core/download/download_manager.py)
		 -> YtDlpRunner (core/download/yt_dlp_runner.py)
		 -> FormatSelector (core/download/format_selector.py)
		 -> (future) Download Profiles from [download.profiles.<name>]
```

Principles
Core logic is UI-independent
CLI and GUI both use the same backend
Focus on modular, reusable functions
Designed for automation and batch processing
Configuration follows predictable precedence for request construction:
CLI values > profile values > global defaults

### Metadata Model: What Changed and Why

This diff adds a dedicated metadata domain layer so movie scraping logic is isolated from video/audit/jellyfin modules.

New model flow:

1. Input parsing:
  - title_parser extracts a clean title and optional year from folder/file names.
2. Discovery:
  - tmdb_provider.search returns ranked candidates as TmdbSearchResult entries.
3. Selection:
  - match_selector picks the best item automatically or via interactive prompt.
4. Enrichment:
  - tmdb_provider.get_movie_metadata maps full cast/crew/ratings/IDs/artwork fields into MovieMetadata.
5. Output generation:
  - nfo_writer writes Jellyfin/Kodi-compatible XML .nfo
  - artwork_downloader saves poster/fanart/logo/etc. in parallel.
6. Orchestration:
  - metadata_pipeline coordinates the full lifecycle and returns PipelineResult with status (SUCCESS, SKIPPED, NOT_FOUND, FAILED).

Why this model helps:

- Clear boundaries: HTTP, parsing, matching, writing, downloading are independent and testable.
- Better batch safety: explicit statuses prevent hidden failures in large NAS runs.
- Future-ready: easy to plug in additional providers or new output targets.

Core Use Cases
1. 🎥 Convert .mp4 → .mkv

Lossless container conversion using ffmpeg
Preserve all streams (audio, subtitles, metadata)
Optional deletion of original file

2. 🔊 Normalize Audio Tracks

Set correct language metadata (e.g. ger, eng)
Set default audio track (e.g. German preferred)
Remove unwanted tracks (optional)

3. 📀 Improve DVD Rips (Upscaling)

Enhance low-resolution content (e.g. 480p → 1080p)
Optional re-encoding with better codecs (H.264 / HEVC)
Potential integration of AI upscaling (future)

4. 🎚️ Merge Multiple Files

Combine multiple .mp4 files into a single .mkv
Example:
File 1 → German audio
File 2 → English audio

Output:
One MKV with multiple audio tracks

5. 🎵 Music & Audiobook Organization

Extract and standardize music metadata (ID3 tags)
Convert audio formats (FLAC, MP3, M4A, etc.)
Organize by artist/album structure
Generate playlists and library statistics
Audiobook chapter detection and metadata

6. 📜 Subtitle Generation & Management

Extract audio from video
Generate subtitles using Whisper
Auto-sync subtitles
Add subtitles to MKV container
Get subtitles via API with download
Convert between subtitle formats (SRT, VTT, ASS, TTML, SCC, STL, LRC, SBV)
Translate subtitles offline with OPUS-MT

7. 🎬 Jellyfin Integration

Connect directly to the Jellyfin REST API
Trigger library scans automatically after pipeline completion
Detect missing metadata (poster, backdrop, description, year)
Find unmatched items and wrong series assignments
Auto-repair fixable issues via forced metadata refresh
Search items and inspect per-library

8. 📂 NAS Automation

Watch folders (e.g. \\TRUENAS\Media\Incoming)
Automatically:
Convert
Clean up
Rename for Jellyfin
Move to correct library folder

9. 🎨 GUI Application (Future) #TODO

Drag & Drop media processing
Visual progress tracking
Presets for common workflows
Built with PySide6 (Qt)

## Installation & Setup

### Prerequisites
- Python 3.11 or higher
- FFmpeg and FFprobe (for media processing)
- git (for cloning the repository)

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/media-tool.git
cd media-tool

# Create and activate virtual environment
python -m venv .venv
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/macOS

# Install development dependencies and the project itself
pip install -r requirements.txt
pip install -e .
```

Notes:
- `pyacoustid` is the installable package name for the Python module imported as `acoustid`
- `requirements.txt` is the recommended dev/test environment because it includes tooling such as `pytest`, `mypy`, and `pre-commit`

### Verify Installation

```bash
media-tool --help  # Shows all available commands
```

## Type Checking

Install development dependencies and the project itself:

```bash
pip install -r requirements.txt
pip install -e .
```

Run mypy manually:

```bash
python -m mypy .
```

Set up the pre-commit hook:

```bash
pre-commit install
pre-commit run --all-files
```

GitHub Actions runs the same mypy command on pushes and pull requests via [.github/workflows/mypy.yml](.github/workflows/mypy.yml).

## Testing

Use the same development environment as above:

```bash
pip install -r requirements.txt
pip install -e .
```

Run the full suite:

```bash
python -m pytest -q
```

Run a focused test file:

```bash
python -m pytest tests/unit/test_acoustid_provider.py -q
```

If you need the AcoustID-related tests manually, install package names exactly as published on PyPI:

```bash
python -m pip install pyacoustid musicbrainzngs
```

The import name in Python remains `acoustid`, but the package name to install is `pyacoustid`.

## Configuration

`media-tool` now supports a central local configuration file for API keys, tool paths, and common defaults.

Why TOML:
- the project already uses TOML in `pyproject.toml`
- Python 3.11+ includes `tomllib`, so no extra parser dependency is needed
- it stays readable for paths, booleans, lists, and nested sections

### Setup

1. Copy `media-tool.example.toml` to `media-tool.toml`
2. Fill in the values you actually use locally
3. Keep `media-tool.toml` private; it is ignored by Git

Example:

```toml
[api]
opensubtitles_api_key = "your-key"
acoustid_api_key = "your-key"

[tools]
ffmpeg = "ffmpeg"
ffprobe = "ffprobe"
yt_dlp = "yt-dlp"

[defaults.subtitles]
languages = ["en", "de"]

[defaults.audio]
min_confidence = 0.8

[download]
default_output_video = "downloads/videos"
default_output_music = "downloads/music"
default_output_series = "downloads/series"
max_resolution = 1080
audio_format = "mp3"
audio_quality = "320k"
preferred_language = "de"
subtitle_languages = ["de", "en"]
embed_subtitles = true
embed_thumbnail = true
sponsorblock_remove = ["sponsor"]
```

### Environment Overrides

You can override the config file path:

```bash
set MEDIA_TOOL_CONFIG=C:\path\to\media-tool.toml
```

You can also override individual settings without editing the file:

```bash
set MEDIA_TOOL_API__OPENSUBTITLES_API_KEY=your-key
set MEDIA_TOOL_DEFAULTS__SUBTITLES__LANGUAGES=en,de
set MEDIA_TOOL_TOOLS__FFMPEG=C:\tools\ffmpeg.exe
set MEDIA_TOOL_TOOLS__YT_DLP=C:\tools\yt-dlp.exe
```

Legacy environment variables still work for compatibility:

```bash
set OPENSUBTITLES_API_KEY=your-key
set ACOUSTID_API_KEY=your-key
set TMDB_API_KEY=your-key
set FFMPEG_BIN=C:\tools\ffmpeg.exe
set FFPROBE_BIN=C:\tools\ffprobe.exe
```

### Current Usage

The subtitle commands now read their OpenSubtitles API key and default language list from config when the CLI options are omitted:

```bash
media-tool subtitle download movie.mkv
```

The audio tagging commands can do the same for `acoustid_api_key`, and the low-level FFmpeg/FFprobe runners now honor configured binary paths globally.

Download commands now read defaults from `[download]` in config (output directories, resolution, audio format/quality, subtitle defaults).
`[tools].yt_dlp` is also available in config for consistency with your shell setup and legacy scripts, even though the download subsystem primarily uses the Python `yt_dlp` package.

Metadata commands read TMDB credentials from config or environment:

- `[api].tmdb_api_key`
- `TMDB_API_KEY`

## Logging

`media-tool` uses centralized logging with Rich console output and optional rotating log files.

Common recipes:

```bash
# Default (warnings + errors only)
media-tool upscale batch "E:\Downloads" -r

# More runtime progress information (INFO)
media-tool --verbose upscale batch "E:\Downloads" -r

# Deep technical diagnostics (DEBUG)
media-tool --debug audio workflow "M:\Music" "M:\Music_Out" --format mp3

# Quiet mode for scripts/cron (warnings + errors)
media-tool --quiet download series "https://youtube.com/playlist?list=..."

# Persist rotating text logs
media-tool --verbose --log-file logs/media-tool.log video inspect "Y:\Videos"

# Persist structured JSON logs (one JSON object per line)
media-tool --debug --log-file logs/media-tool.jsonl --log-json subtitle download movie.mkv
```

Global logging flags:

- `--verbose` / `-v`: INFO-level runtime progress
- `--debug`: DEBUG-level internals
- `--quiet` / `-q`: warnings and errors only
- `--log-file PATH`: write rotating logs to file
- `--log-json`: JSON format for file logs (requires `--log-file`)

## Quick Start & Common Workflows

### 1. Video Processing

#### Convert Single Video (MP4 → MKV)
```bash
media-tool video convert input.mp4 output.mkv --language de
```

#### Batch Convert Directory
```bash
media-tool video convert "C:\Downloads" --output "D:\Videos" --language de
```

#### Merge Multiple Audio Tracks
```bash
media-tool video merge "C:\Path\To\Movie" output.mkv
```

#### Upscale DVD Quality (480p → 720p)
```bash
media-tool video upscale input.mp4 output.mp4 --height 720
```

#### Analyze Video Library
```bash
media-tool video inspect "Y:\Videos" --output video_library.csv
```

#### Generate Subtitles with Whisper (single file)
```bash
media-tool video subtitle movie.mkv --language en
```

#### Generate Subtitles – Batch (Directory)
```bash
media-tool video subtitle "Season 01/" --recursive
```

Available Whisper models: `tiny`, `base`, `small`, `medium`, `large-v3` (default).

#### Auto-Generate English Subtitles only where needed
```bash
media-tool video subtitle-auto "C:\Movies" --recursive
```

Checks every MKV:
1. Has the file an **English audio** track? (skip if not)
2. Does it **already have English subtitles**? (skip if yes)

Only files that need subtitles are transcribed.

```bash
# Preview what would be processed (no changes)
media-tool video subtitle-auto "C:\Movies" --recursive --dry-run

# Re-generate even if subtitles already exist
media-tool video subtitle-auto "C:\Movies" --recursive --overwrite
```
---------------------------------------------------------------------------
 Upscale profiles

 Built-in profiles (use with --profile):
   dvd       Standard DVD → 720p H.265  (CRF 21, preset medium)
   dvd-hq    High quality              (CRF 18, preset slow)
   dvd-fast  Fast NAS batch            (CRF 23, preset fast)
   1080p     Full HD upscale           (CRF 20, preset medium, 1080p)
   anime     Animated content          (CRF 19, preset slow, cropdetect off)
   archive   Maximum quality archival  (CRF 14, preset veryslow)

 Run 'media-tool upscale profiles' to see all profiles with full details.
 ---------------------------------------------------------------------------

 The [upscale] section is reserved for future global upscale defaults.
 [upscale]
 default_profile = "dvd"

### 2. Music Library Processing

#### Scan and Analyze Music Library
```bash
media-tool audio scan "M:\Music" --output music_library.csv
```

Generates a detailed CSV report with file properties, tags, technical audio specs, derived fields, and per-file error details for large-library analysis or migration.

```bash
media-tool audio scan "M:\Music" --output music_library.csv --max-workers 8
```

#### Convert Audio Formats (to FLAC)
```bash
media-tool audio convert "M:\Music" --format flac --output "N:\Converted"
```

#### Organize by Artist/Album Structure
```bash
media-tool audio organize "M:\Music" --format flac
```

#### Enhance Single Audio File
```bash
media-tool audio improve "song.mp3" "song_improved.mp3"
```

#### Complete Music Workflow (Scan → Convert → Organize)
```bash
media-tool audio workflow "M:\Mixed_Music" "M:\Organized_Music" --format flac
```

#### Scan-Only Mode (Preview without changes)
```bash
media-tool audio workflow "M:\Music" "M:\Output" --scan-only
```

### 3. Audiobook Processing

#### Scan Audiobook Library
```bash
media-tool audiobook scan "M:\Audiobooks" --output audiobooks_library.csv
```

#### Organize Audiobooks by Author/Title
```bash
media-tool audiobook organize "M:\Audiobooks" --format m4a
```

#### Merge Chapter Files into Single Audiobook
```bash
media-tool audiobook merge "C:\Chapters" "output.m4a"
```

#### Preview Merge (Dry-Run)
```bash
media-tool audiobook merge "C:\Chapters" "output.m4a" --dry-run
```

#### Merge to MP3 with Overwrite
```bash
media-tool audiobook merge "C:\Chapters" "output.mp3" --format mp3 --overwrite
```

### 4. Subtitle Management

#### Download Subtitles from OpenSubtitles.org
```bash
# Single file – auto-select best English subtitle
media-tool subtitle download movie.mkv

# Multiple preferred languages (priority order)
media-tool subtitle download movie.mkv --languages en,de

# Interactive selection (show all matches, let user choose)
media-tool subtitle download movie.mkv --interactive

# Entire directory (recursive by default)
media-tool subtitle download "C:\Movies"
```

Requires an [OpenSubtitles API key](https://www.opensubtitles.com/api).
Set it in `media-tool.toml` under `[api].opensubtitles_api_key` or via env var `OPENSUBTITLES_API_KEY`.

#### Search Subtitles (without downloading)
```bash
# Check availability before batch processing
media-tool subtitle search movie.mkv
media-tool subtitle search movie.mkv --languages en,de --limit 20
```

#### Convert Subtitle Formats
```bash
# Convert a single file to a different format
media-tool subtitle convert movie.srt --to vtt
media-tool subtitle convert movie.ass --to srt --output movie_clean.srt

# Batch convert all subtitles in a directory
media-tool subtitle convert "C:\Movies" -r --to srt

# Preview without writing
media-tool subtitle convert movie.ass --to srt --dry-run

# List all supported formats with read/write status
media-tool subtitle formats
```

Supported formats:

| Format | Extension | Read | Write | Notes |
|---|---|---|---|---|
| SRT | `.srt` | ✅ | ✅ | SubRip — most widely supported |
| WebVTT | `.vtt` | ✅ | ✅ | HTML5 / streaming |
| ASS/SSA | `.ass`, `.ssa` | ✅ | ✅ | Advanced SubStation Alpha (styles preserved) |
| TTML/DFXP | `.ttml`, `.dfxp` | ✅ | ✅ | Broadcast / streaming standard |
| SCC | `.scc` | ✅ | ✅ | Scenarist Closed Caption (CEA-608) |
| STL | `.stl` | ✅ | ✅ | EBU STL broadcast format |
| LRC | `.lrc` | ✅ | ✅ | Lyric format for music |
| SBV | `.sbv` | ✅ | ✅ | YouTube caption format |

#### Translate Subtitles Offline (no API key required)
```bash
# Single file: English → German
media-tool subtitle translate movie.en.srt --from en --to de

# German → English
media-tool subtitle translate movie.de.srt --from de --to en

# Directory: translate all subtitle files recursively
media-tool subtitle translate "C:\Movies" -r --from en --to de

# Preview without writing
media-tool subtitle translate movie.en.srt --from en --to de --dry-run

# CPU-only fallback (no CUDA/GPU required)
media-tool subtitle translate movie.en.srt --from en --to de --backend argos
```

Output naming convention: `movie.en.srt` → `movie.de.srt` (language suffix replaced).

Install the required backend first:
```bash
# GPU-accelerated (recommended — ~500 seg/s on GPU)
pip install ctranslate2 transformers sentencepiece

# CPU fallback (no CUDA needed)
pip install argostranslate
```

### 5. Batch Operations & Automation

#### Batch Process All Videos in Directory
```bash
media-tool video convert "E:\Downloads" --output "Y:\Videos" --language de --overwrite
```

#### DVD Batch Upscaling (auto-skips existing 720p+)
```bash
media-tool video upscale batch "E:\Downloads" --height 720
```

### 6. Web Download Workflows (yt-dlp)

#### Download Single Video
```bash
media-tool download video "https://youtube.com/watch?v=..." --resolution 1080
```

#### Download with Browser Cookies (for login-protected media)
```bash
media-tool download video "https://youtube.com/watch?v=..." --cookies-from-browser chrome
```

#### Download with Cookie File
```bash
media-tool download video "https://youtube.com/watch?v=..." --cookies-file cookies.txt
```

#### Download Music as FLAC
```bash
media-tool download music "https://soundcloud.com/..." --format flac
```

The downloader retries automatically with browser cookies when a login/authentication error is detected and no cookie source was explicitly provided.
Cookie values are not persisted by the tool and should only be passed at runtime.

#### Download Series/Playlist Structure
```bash
media-tool download series "https://youtube.com/playlist?list=..." --output "Y:\Serien"
```

### 7. Metadata & Artwork (TMDB)

#### Search only (no file output)
```bash
media-tool metadata search "Inception" --year 2010
```

#### Fetch metadata + artwork for one movie file
```bash
media-tool metadata fetch "Y:\Filme\Inception (2010)\Inception (2010).mkv"
```

#### Batch process an entire movie library
```bash
media-tool metadata fetch "Y:\Filme"
```

#### Interactive match selection
```bash
media-tool metadata fetch "Y:\Filme" --interactive
```

#### Include all artwork types and overwrite existing files
```bash
media-tool metadata fetch "Y:\Filme" --artwork all --overwrite
```

#### Preview only (dry run)
```bash
media-tool metadata fetch "Y:\Filme" --dry-run
```

Generated output per movie directory typically includes:

- MovieName (Year).nfo
- poster.jpg
- fanart.jpg
- optional artwork depending on --artwork selection (logo, thumb, banner, disc)

## All Available Commands

```bash
media-tool --help              # General help
media-tool video --help        # Video commands
media-tool audio --help        # Audio/Music commands
media-tool audiobook --help    # Audiobook commands
media-tool inspect --help      # Inspection tools
media-tool subtitle --help     # Subtitle commands
media-tool download --help     # yt-dlp based download commands
media-tool jellyfin --help     # Jellyfin library management
media-tool metadata --help     # TMDB metadata + artwork commands
media-tool workflow --help     # End-to-end workflow commands
media-tool audit --help        # Library audit and quality checks
```

### `media-tool video` commands

| Command | Description |
|---|---|
| `video convert <input> <output>` | Lossless MP4 → MKV container conversion, preserves all streams |
| `video inspect <dir>` | Scan directory and export metadata to CSV |
| `video merge <dir> <output>` | Merge German + English MP4 into dual-audio MKV |
| `video upscale <input> <output>` | Upscale DVD-quality (480p) to 720p/1080p H.265 |
| `video subtitle <input>` | Generate subtitles via Whisper AI (single file or directory) |
| `video subtitle-auto <input>` | Auto-generate English subtitles only where missing & English audio exists |
| `video subtitle-translate <input>` | Translate subtitle files offline (no API key required) |

### `media-tool subtitle` commands

| Command | Description |
|---|---|
| `subtitle download <path>` | Download subtitles from OpenSubtitles.org and embed into MKV |
| `subtitle search <file>` | Search OpenSubtitles.org and show results (no download) |
| `subtitle translate <path>` | Translate SRT/ASS/VTT files offline with Helsinki-NLP OPUS-MT or argostranslate |
| `subtitle convert <path>` | Convert subtitle files between formats (SRT, VTT, ASS, TTML, SCC, STL, LRC, SBV) |
| `subtitle formats` | List all supported subtitle formats with read/write status |

### `media-tool jellyfin` commands

| Command | Description |
|---|---|
| `jellyfin ping` | Check server connectivity and API key validity |
| `jellyfin refresh` | Refresh library / single library / single item |
| `jellyfin scan-status` | Show current scan progress (live with `--watch`) |
| `jellyfin libraries` | List all libraries with paths and item counts |
| `jellyfin inspect` | Find metadata problems + optional auto-fix (`--fix`) |
| `jellyfin fix-series` | Reassign a mismatched episode to the correct series |
| `jellyfin search` | Search items by name (returns IDs for other commands) |

### `media-tool metadata` commands

| Command | Description |
|---|---|
| `metadata search <title>` | Search TMDB and list candidates without writing files |
| `metadata fetch <path>` | Fetch TMDB metadata, write .nfo, and download artwork |

### 7. Jellyfin Library Management

#### Check connectivity
```bash
media-tool jellyfin ping
```

#### Trigger a library refresh
```bash
# Refresh everything
media-tool jellyfin refresh

# Refresh a single named library
media-tool jellyfin refresh --library Movies

# Refresh a single item by ID
media-tool jellyfin refresh --item abc123

# Trigger and wait until the scan finishes
media-tool jellyfin refresh --wait
```

#### Monitor scan progress
```bash
media-tool jellyfin scan-status
media-tool jellyfin scan-status --watch          # live updates every 5 s
media-tool jellyfin scan-status --watch --interval 10
```

#### List all libraries
```bash
media-tool jellyfin libraries
```

#### Inspect metadata quality
```bash
# Find all problems across the entire library
media-tool jellyfin inspect

# Only movies, auto-fix resolvable issues
media-tool jellyfin inspect --kind movies --fix

# Scope to one library, export CSV report
media-tool jellyfin inspect -l Movies --export issues.csv
```

Detected issue types: `missing_poster`, `missing_backdrop`, `missing_overview`, `missing_year`, `unmatched` (no TMDB/IMDB IDs), `wrong_series_match`, `missing_episode_number`, `duplicate_item`.

Auto-fixable issues (poster, backdrop, overview, year) are resolved by triggering a forced metadata refresh. Duplicates and wrong series assignments are reported only.

#### Find and fix a mismatched episode
```bash
# Step 1 — find the item IDs
media-tool jellyfin search "Better Call Saul" --type series
media-tool jellyfin search "pilot" --type episode

# Step 2 — reassign
media-tool jellyfin fix-series <episode-id> <correct-series-id>
```

#### Automatic refresh after workflow pipeline

When `[jellyfin]` is configured in `media-tool.toml`, the workflow pipeline automatically triggers a Jellyfin refresh after successful completion:

```toml
[jellyfin]
base_url      = "http://192.168.1.100:8096"
api_key       = "your-api-key"
wait_for_scan = false

[jellyfin.auto_trigger]
enabled         = true
on_success_only = true
```

No extra flags needed — the pipeline picks it up automatically.

### 8. Translation model comparison

#### Translation model comparison

| Model | Size | VRAM | Speed (GPU) | Quality |
|---|---|---|---|---|
| `opus-mt-de-en` / `opus-mt-en-de` (standard) | ~300 MB | ~0.5 GB | ~500 seg/s | Very good |
| `opus-mt-tc-big-de-en` / `opus-mt-tc-big-en-de` (big) | ~900 MB | ~1.5 GB | ~200 seg/s | Excellent |

`big` models are trained on TED Talks + OpenSubtitles — ideal for film subtitles.
