# Subtitles Module

## Responsibilities

The subtitle domain combines **two closely related subsystems**:

1. `core/subtitles` — acquisition and embedding of subtitle files
2. `core/translation` — format-aware subtitle parsing, translation, and rewriting

This split keeps remote provider logic separate from local language-processing logic.

---

## Package Layout

| Area | Key files | Responsibility |
|---|---|---|
| Acquisition | `subtitle_provider.py`, `opensubtitles_provider.py`, `subtitle_downloader.py` | provider abstraction, search, download, embed |
| Translation | `subtitle_translator.py`, `translator_factory.py`, `chunking.py`, `models.py` | parse -> translate -> restore formatting -> write |
| Format support | `format_registry.py`, `subtitle_parser.py`, `subtitle_writer.py`, `formats/` | normalize many subtitle formats through one intermediate model |

---

## Acquisition Path

The acquisition side centers on the `SubtitleProvider` contract and the concrete `OpenSubtitlesProvider` implementation.

### Provider model

`subtitle_provider.py` defines three important data contracts:

- `MovieInfo` — file path, hash, file size, duration, optional IMDb/TMDB/title hints
- `SubtitleMatch` — one candidate subtitle returned by a provider
- `DownloadResult` — result of a search/download/embed attempt

### `OpenSubtitlesProvider` behavior

The current implementation searches using a preference order described in code comments:

1. file hash
2. IMDb/TMDB ids when available
3. filename/title fallback

Candidate ranking is then refined using:

- hearing-impaired preference
- release-name matching when available
- rating and download count

### Embedding

The downloader flow integrates with `FFmpegMuxer.add_subtitle_to_mkv(...)` to mux subtitles back into MKV containers with language/title metadata.

---

## Translation Path

`SubtitleTranslator` is the main orchestration class for local subtitle translation.

### Translation pipeline

```text
parse -> extract tags -> build chunks -> translate -> split results -> restore tags -> wrap lines -> write file
```

### Key implementation details

- **format-independent model**: the translator works on `SubtitleDocument` and `SubtitleSegment`, not directly on raw file syntax
- **context-aware chunking**: `build_chunks()` groups nearby segments to preserve context
- **tag preservation**: `TagProcessor` replaces ASS/HTML tags with placeholders before translation and restores them afterward
- **translation cache**: repeated strings can be reused instead of translated again
- **optional language detection**: if `langdetect` is installed and enabled, the source language can be auto-detected

---

## Data Models

The translation layer is centered on `core/translation/models.py`.

| Model | Purpose |
|---|---|
| `SubtitleFormat` | format classification (`srt`, `ass`, `vtt`, `ttml`, etc.) |
| `SubtitleSegment` | one subtitle block with text, timing, and preserved style/tag info |
| `SubtitleDocument` | format-independent subtitle representation |
| `LanguagePair` | source/target language pair |
| `TranslationRequest` / `TranslationResult` | orchestration input/output |
| `StyleInfo`, `PositionInfo` | format-preserving metadata for richer subtitle formats |

### Important limitation

`SubtitleFormat` distinguishes **text-based** and **bitmap-based** subtitle formats. Bitmap formats like `.sub` and `.sup` are not directly translatable as plain text.

---

## Backend Strategy

`translator_factory.py` currently supports two backends:

- `opus-mt` via `OpusMtTranslator`
- `argos` via `ArgosTranslator`

The factory returns a `TranslatorProtocol`, so higher layers remain backend-agnostic.

---

## External Dependencies

- **OpenSubtitles API** for provider-backed subtitle search/download
- **ffmpeg** for embedding subtitle streams into MKV containers
- optional **langdetect** for source-language detection
- local translation backends for offline or semi-offline translation workflows

---

## Operational Notes

- the workflow step `s05_subtitles.py` uses OpenSubtitles when configured
- Whisper fallback is mentioned in code comments as a future/implementation-dependent path and is not yet a fully integrated default in the workflow step
- translation is designed to preserve timing and formatting, not just raw text content

This module is therefore one of the clearest examples of the project’s balance between **external provider orchestration** and **local, format-aware processing**.
