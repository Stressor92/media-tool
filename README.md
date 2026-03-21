🎬 media-tool

Tools and scripts for preparing media, movies, TV shows, music, and audiobooks for Jellyfin and NAS archiving.

Vision

This project aims to evolve from simple scripts into a modular, extensible media processing toolkit with:
CLI interface (first stage)
Automated workflows for NAS environments
Future GUI application
Integration with tools like ffmpeg, Whisper, and Jellyfin

Architecture

The project follows a layered architecture:

src/
│
├── core/        # Business logic (independent of UI)
├── cli/         # Command-line interface (Typer)
├── utils/       # Shared helpers (ffmpeg, file handling)
├── gui/         # (future) graphical interface

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

Planned Features

Batch processing of large media collections
Logging and error handling (rich output)
Config system (profiles for encoding, languages, etc.)
Plugin-like architecture for extensions
Jellyfin-compatible naming automation

Additional Ideas

Hier ein paar starke Erweiterungen für später:

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

pip install -e .

Alle verfügbaren Befehle auf einen Blick
```
media-tool --help
media-tool convert --help
media-tool merge --help
media-tool upscale --help
media-tool inspect --help

MP4 → MKV (lossless, Deutsch-Metadata)

# Mit englischer Tonspur:
media-tool convert batch "C:\Users\hille\Downloads" --language de --audio-title Deutsch

# Automatisch (erkennt -de / -en Suffix):
media-tool merge auto "C:\Users\hille\Downloads\Talk to Me (2022)"

# NAS Film Liste erstellen, CSV daneben speichern:
media-tool inspect scan "Y:\"

# DVD-Upscale H.265 720p Ganzer Ordner (überspringt automatisch alles >= 720p):
media-tool upscale batch "E:\Downloads"

# Musik-Bibliothek analysieren und CSV erstellen:
media-tool audio scan "M:\Music" --output music_library.csv

# Audio-Dateien in FLAC konvertieren:
media-tool audio convert "M:\Music" --format flac --output "N:\Converted"

# Musik-Dateien in Jellyfin-Struktur organisieren:
media-tool audio organize "M:\Music" --format flac

# Einzelne Musik-Datei verbessern:
media-tool audio improve "song.mp3" "song_improved.mp3"

# Musik-Bibliothek verbessern:
media-tool audio improve-library ~/Music ~/Music_Improved

# Komplette Musik-Bibliothek verarbeiten:
media-tool audio workflow ~/Mixed_Music ~/Organized_Music --format flac

# Scan-only mode für Musik-Bibliothek:
media-tool audio workflow ~/Mixed_Music ~/Organized_Music --scan-only

# Hörbuch-Bibliothek analysieren:
media-tool audiobook scan "M:\Audiobooks" --output audiobooks_library.csv

# Hörbücher in Jellyfin-Struktur organisieren:
media-tool audiobook organize "M:\Audiobooks" --format flac

# Video-Dateien konvertieren:
media-tool video convert input.mp4 output.mkv --language de

# Video-Bibliothek analysieren:
media-tool video inspect "Y:\Videos" --output video_list.csv

# Videos zusammenführen:
media-tool video merge "C:\Downloads\Movie" output.mkv

# Video upscalen:
media-tool video upscale input.mp4 output.mp4 --height 720

# Music processing
media-tool audio scan <dir>        # Scan music library
media-tool audio organize <src> <dst>  # Organize into Artist/Album structure  
media-tool audio improve <file> <output>  # Enhance single file
media-tool audio workflow <src> <dst>  # Complete music processing

# Video processing  
media-tool video convert <input> <output>  # MP4 → MKV conversion
media-tool video inspect <dir>     # Scan video library
media-tool video merge <dir> <output>  # Merge dual-audio files
media-tool video upscale <input> <output>  # DVD → 720p upscaling

# Audiobook processing
media-tool audiobook scan <dir>    # Scan audiobook library
media-tool audiobook organize <src> <dst>  # Organize into Author/Book structure
media-tool audiobook merge <src> <dst>     # Merge chapter files into single audiobooks

# Preview what would be merged
python -m src.cli.main audiobook merge /path/to/chapters /path/to/output --dry-run

# Merge chapters into M4A files (default)
python -m src.cli.main audiobook merge /path/to/chapters /path/to/output

# Merge to MP3 format with overwrite
python -m src.cli.main audiobook merge /path/to/chapters /path/to/output --format mp3 --overwrite