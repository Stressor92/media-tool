🎬 media-tool

Tools and scripts for preparing media, movies, TV shows, music, and audiobooks for Jellyfin and NAS archiving.

Vision

This project aims to evolve from simple scripts into a modular, extensible media processing toolkit with:
CLI interface (first stage)
Automated workflows for NAS environments
Future GUI application
Integration with tools like ffmpeg, Whisper, and Jellyfin

Architecture

The project follows a layered architecture designed for modularity, extensibility, and separation of concerns:

src/
│
├── core/           # Business logic (independent of UI/CLI)
│   ├── audio/      # Audio processing modules (conversion, enhancement, metadata)
│   ├── video/      # Video processing modules (conversion, upscaling, merging)
│   ├── audiobook/  # Audiobook-specific logic (organization, chapter merging)
│   └── naming/     # File naming and organization utilities for Jellyfin compatibility
├── cli/            # Command-line interface (Typer-based)
│   ├── main.py     # Main CLI entry point and command dispatcher
│   ├── audio_cmd.py, audiobook_cmd.py, convert_cmd.py, etc.  # Specific command implementations
├── utils/          # Shared helpers and low-level utilities
│   ├── audio_analyzer.py  # Audio metadata extraction using ffprobe
│   ├── ffmpeg_runner.py, ffprobe_runner.py  # FFmpeg/FFprobe wrappers for media processing
│   └── audio_processor.py  # Audio manipulation and enhancement tools
├── gui/            # (future) Graphical user interface (PySide6/Qt for drag-and-drop workflows)
│
tests/              # Comprehensive test suite for reliability
├── unit/           # Unit tests for individual functions and modules
└── integration/    # Integration tests for full workflows and CLI commands
│
obsolet_ps_scrips/  # Legacy PowerShell scripts (deprecated, replaced by Python modules)

Principles
Core logic is UI-independent
CLI and GUI both use the same backend
Focus on modular, reusable functions
Designed for automation and batch processing

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

6. 📜 Subtitle Generation (Future)

Extract audio from video
Generate subtitles using Whisper
Auto-sync subtitles
Add subtitles to MKV container

7. 📂 NAS Automation

Watch folders (e.g. \\TRUENAS\Media\Incoming)
Automatically:
Convert
Clean up
Rename for Jellyfin
Move to correct library folder

8. 🎨 GUI Application (Future)

Drag & Drop media processing
Visual progress tracking
Presets for common workflows
Built with PySide6 (Qt)

## Installation & Setup

### Prerequisites
- Python 3.10 or higher
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

# Install in development mode
pip install -e .
```

### Verify Installation

```bash
media-tool --help  # Shows all available commands
```

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

### 2. Music Library Processing

#### Scan and Analyze Music Library
```bash
media-tool audio scan "M:\Music" --output music_library.csv
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

### 4. Batch Operations & Automation

#### Batch Process All Videos in Directory
```bash
media-tool video convert "E:\Downloads" --output "Y:\Videos" --language de --overwrite
```

#### DVD Batch Upscaling (auto-skips existing 720p+)
```bash
media-tool video upscale batch "E:\Downloads" --height 720
```

## All Available Commands

```bash
media-tool --help              # General help
media-tool video --help        # Video commands
media-tool audio --help        # Audio/Music commands
media-tool audiobook --help    # Audiobook commands
media-tool inspect --help      # Inspection tools
```

## Planned Features

- Batch processing of large media collections
- Logging and error handling (rich output)
- Config system (profiles for encoding, languages, etc.)
- Plugin-like architecture for extensions
- Jellyfin-compatible naming automation

## Future Enhancements

### 🔎 Smart Media Analysis

🔎 Media Analysis

Automatisch erkennen:
Auflösung
Audio-Sprachen
Subtitle-Sprachen
Entscheidung treffen:
→ z. B. „nur konvertieren wenn nicht mkv“

🧠 Smart Processing

Wenn Datei schon optimal → überspringen
Wenn Audio fehlt → ergänzen
Wenn Subtitles fehlen → generieren

🏷️ Jellyfin Naming

Automatische Umbenennung:
Movie Name (Year)/Movie Name (Year).mkv
🌐 Subtitle Download
Integration mit OpenSubtitles API
Automatische Sprach-Auswahl
