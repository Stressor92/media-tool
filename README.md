# 🎬 media-tool

Tools and scripts for preparing media, movies, TV shows, music, and audiobooks for Jellyfin and NAS archiving.

## Vision

This project aims to evolve from simple scripts into a modular, extensible media processing toolkit with:
- CLI interface (first stage)
- Automated workflows for NAS environments
- Future GUI application
- Integration with tools like ffmpeg, Whisper, and Jellyfin

## Architecture

The project follows a layered architecture designed for modularity, extensibility, and separation of concerns:

```
src/
├── core/           # Business logic (independent of UI/CLI)
│   ├── audio/      # Audio processing modules (conversion, enhancement, metadata)
│   ├── video/      # Video processing modules (conversion, upscaling, merging)
│   ├── audiobook/  # Audiobook-specific logic (organization, chapter merging)
│   └── naming/     # File naming and organization utilities for Jellyfin compatibility
├── cli/            # Command-line interface (Typer-based)
│   ├── main.py     # Main CLI entry point and command dispatcher
│   ├── audio_cmd.py, audiobook_cmd.py, video_cmd.py, etc.
│   └── (module-specific command implementations)
├── utils/          # Shared helpers and low-level utilities
│   ├── audio_analyzer.py    # Audio metadata extraction using ffprobe
│   ├── ffmpeg_runner.py     # FFmpeg wrapper for media processing
│   ├── ffprobe_runner.py    # FFprobe wrapper for media inspection
│   └── audio_processor.py   # Audio manipulation and enhancement tools
├── gui/            # (future) Graphical user interface (PySide6/Qt)
│
tests/              # Comprehensive test suite
├── unit/           # Unit tests for individual functions
└── integration/    # Integration tests for full workflows

obsolete_ps_scripts/  # Legacy PowerShell scripts (deprecated)
```

### Design Principles
- **Core logic is UI-independent**: Business logic in `core/` doesn't depend on CLI or GUI
- **CLI and GUI share the same backend**: Both interfaces use the same core modules
- **Modular and reusable**: Each module has a single responsibility
- **Designed for automation**: Batch processing and scripting in mind

## Core Use Cases

### 1. 🎥 Convert .mp4 → .mkv
- Lossless container conversion using ffmpeg
- Preserve all streams (audio, subtitles, metadata)
- Optional deletion of original file

### 2. 🔊 Normalize Audio Tracks
- Set correct language metadata (e.g., ger, eng)
- Set default audio track (e.g., German preferred)
- Remove unwanted tracks (optional)

### 3. 📀 Improve DVD Rips (Upscaling)
- Enhance low-resolution content (e.g., 480p → 1080p)
- Optional re-encoding with better codecs (H.264 / HEVC)
- Potential integration of AI upscaling (future)

### 4. 🎚️ Merge Multiple Files
- Combine multiple .mp4 files into a single .mkv
- Example: File 1 (German) + File 2 (English) → One MKV with multiple audio tracks

### 5. 🎵 Music & Audiobook Organization
- Extract and standardize music metadata (ID3 tags)
- Convert audio formats (FLAC, MP3, M4A, etc.)
- Organize by artist/album structure
- Audiobook chapter detection and metadata
- Generate library statistics and playlists

### 6. 📜 Subtitle Generation (Future)
- Extract audio from video
- Generate subtitles using Whisper
- Auto-sync subtitles
- Add subtitles to MKV container

### 7. 📂 NAS Automation (Future)
- Watch folders for incoming media
- Automatic conversion, cleanup, and organization
- Jellyfin-compatible naming and structure

### 8. 🎨 GUI Application (Future)
- Drag & Drop media processing
- Visual progress tracking
- Presets for common workflows

## Installation & Setup

### Prerequisites
- **Python 3.10 or higher**
- **FFmpeg & FFprobe** - Required for all media operations
- **git** - For cloning the repository

### Installation Steps

```bash
# Clone the repository
git clone https://github.com/yourusername/media-tool.git
cd media-tool

# Create virtual environment
python -m venv .venv

# Activate virtual environment
.venv\Scripts\activate              # Windows
source .venv/bin/activate           # Linux/macOS

# Install in development mode
pip install -e .

# Verify installation
media-tool --help
```

## Quick Start & Usage Examples

### 1. Video Processing

**Convert Single Video (MP4 → MKV)**
```bash
media-tool video convert input.mp4 output.mkv --language de
```

**Batch Convert Directory**
```bash
media-tool video convert "C:\Downloads" --output "D:\Videos" --language de
```

**Merge Multiple Audio Tracks**
```bash
media-tool video merge "C:\Path\To\Movie" output.mkv
```

**Upscale DVD Quality (480p → 720p)**
```bash
media-tool video upscale input.mp4 output.mp4 --height 720
```

**Analyze Video Library (Generate CSV Report)**
```bash
media-tool video inspect "Y:\Videos" --output video_library.csv
```

### 2. Music Library Processing

**Scan and Analyze Music Library**
```bash
media-tool audio scan "M:\Music" --output music_library.csv
```

**Convert Audio Formats (entire directory to FLAC)**
```bash
media-tool audio convert "M:\Music" --format flac --output "N:\Converted"
```

**Organize by Artist/Album Structure**
```bash
media-tool audio organize "M:\Music" --format flac
```

**Enhance Single Audio File**
```bash
media-tool audio improve "song.mp3" "song_improved.mp3"
```

**Complete Music Workflow (Scan → Convert → Organize)**
```bash
media-tool audio workflow "M:\Mixed_Music" "M:\Organized_Music" --format flac
```

**Preview Changes Without Modifications (Scan-Only Mode)**
```bash
media-tool audio workflow "M:\Music" "M:\Output" --scan-only
```

### 3. Audiobook Processing

**Scan Audiobook Library**
```bash
media-tool audiobook scan "M:\Audiobooks" --output audiobooks.csv
```

**Organize Audiobooks by Author/Title**
```bash
media-tool audiobook organize "M:\Audiobooks" --format m4a
```

**Merge Chapter Files into Single Audiobook**
```bash
media-tool audiobook merge "C:\Chapters" "output.m4a"
```

**Preview What Will Be Merged (Dry-Run)**
```bash
media-tool audiobook merge "C:\Chapters" "output.m4a" --dry-run
```

**Merge to MP3 Format with Overwrite**
```bash
media-tool audiobook merge "C:\Chapters" "output.mp3" --format mp3 --overwrite
```

### 4. Batch Operations & Advanced Usage

**Batch Process All Videos in Directory**
```bash
media-tool video convert "E:\Downloads" --output "Y:\Videos" --language de --overwrite
```

**DVD Batch Upscaling (automatically skips files already 720p or higher)**
```bash
media-tool video upscale batch "E:\Downloads" --height 720
```

**Complete Audiobook Workflow**
```bash
media-tool audiobook workflow "M:\Raw_Audiobooks" "M:\Organized_Audiobooks" --format flac
```

## Available Commands Reference

```bash
# General help
media-tool --help

# Module-specific help
media-tool video --help              # Video operations
media-tool audio --help              # Music/Audio operations
media-tool audiobook --help          # Audiobook operations
media-tool inspect --help            # Library inspection
```

## Planned Features

- ✅ Batch processing of large media collections
- ⏳ Logging and error handling (rich output)
- ⏳ Config system (profiles for encoding, languages, etc.)
- ⏳ Plugin-like architecture for extensions
- ⏳ Jellyfin-compatible naming automation
- ⏳ NAS watch folder integration

## Future Enhancements

### 🔎 Smart Media Analysis
- Auto-detect resolution, audio languages, subtitle languages
- Skip conversion if file already meets quality standards
- Decision logic: "Only convert non-MKV files" or "Skip if 1080p+"

### 🧠 Intelligent Processing
- Skip files that already meet optimal criteria
- Auto-supplement missing audio tracks
- Auto-generate subtitles (Whisper integration)
- Smart quality detection before conversion

### 🏷️ Jellyfin Naming & Organization
- Automatic renaming: `Movie Name (Year)/Movie Name (Year).mkv`
- TV series pattern support: `Series Name/Season 01/Episode Title.mkv`
- Movie/Series metadata extraction for Jellyfin import

### 🌐 Subtitle Management
- OpenSubtitles API integration
- Auto-language detection and selection
- Subtitle extraction and embedding in containers
- Multiple language subtitle support

### 📂 NAS Watch Folder Automation
- Real-time folder monitoring for incoming files
- Automatic processing pipeline
- Error notifications and recovery
- Configurable scheduling and resource management

## Development & Testing

### Running Tests

```bash
# Run all tests
pytest

# Run only unit tests
pytest tests/unit

# Run only integration tests
pytest tests/integration

# Verbose output
pytest -v

# Run specific test file
pytest tests/unit/test_audio_analyzer.py
```

### Generate Coverage Report

```bash
pytest --cov=src --cov-report=html
# Opens in htmlcov/index.html
```

### Code Quality

```bash
# Check code style
flake8 src/

# Type checking
mypy src/
```

## Contributing

Contributions are welcome! Please follow these steps:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Add tests for new functionality
4. Commit your changes (`git commit -m 'Add amazing feature'`)
5. Push to the branch (`git push origin feature/amazing-feature`)
6. Open a Pull Request

### Development Guidelines
- Write tests for all new features
- Ensure code passes `pytest` and style checks
- Update documentation for user-facing changes
- Keep commits clean and descriptive

## Troubleshooting

### FFmpeg not found
- Ensure FFmpeg and FFprobe are installed and in your PATH
- Windows: Download from https://ffmpeg.org/download.html
- Linux: `sudo apt-get install ffmpeg`
- macOS: `brew install ffmpeg`

### Import errors
- Ensure virtual environment is activated
- Run `pip install -e .` to reinstall package

### Permission errors on Windows
- Run PowerShell as Administrator
- Check file permissions in target directory

## License

See [LICENSE](LICENSE) for details.

## Support & Community

For issues, questions, or feature requests, please open an issue on GitHub.

---

**Last Updated**: March 2026  
**Project Status**: Active Development - CLI Stage
