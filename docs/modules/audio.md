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
| `genre_normalizer.py` | normalize GENRE tags via explicit taxonomy, alias mapping, and CSV reporting |
| `bpm_tagger.py` | analyze tempo from MP3 audio and write TBPM metadata tags |
| `mp3gain_normalizer.py` | normalize MP3 loudness via MP3Gain without re-encoding |
| `conversion.py` | codec/container conversion workflows |
| `enhancement.py` | loudness, cleanup, and ffmpeg-based enhancement filters |
| `organization.py` | filesystem organization of audio collections |
| `unsorted_music_organizer.py` | threshold-based sorting from unsorted folders into artist/album trees |
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

### BPM metadata tagging (MP3)

`BPMTagger` adds a dedicated path for BPM maintenance on MP3 files:

1. inspect existing `TBPM` values
2. analyze tempo from the audio signal (librosa)
3. cross-check independent tempo estimates for stability
4. write only the `TBPM` ID3 frame in-place

Safety characteristics:

- no re-encoding and no container conversion
- non-MP3 files are skipped
- existing BPM values are preserved unless overwrite is requested
- batch mode processes directories recursively with per-file status reporting
- when direct MP3 decoding fails in the analysis backend, a temporary ffmpeg WAV fallback is used for robust tempo extraction

### Genre normalization (MP3/FLAC/M4A/OGG)

`GenreNormalizer` provides deterministic GENRE normalization for curated libraries:

1. parse incoming genre tags with separator cleanup (`/`, `\\`, `,`, and spaced `&`)
2. map known spelling variants via `config/genre_aliases.json`
3. resolve canonical values from `config/genres.json`
4. expand explicit parent genres before child genres
5. preserve unknown values while reporting them in `unknown_genres.csv`
6. write tags only in apply mode; default mode stays dry-run

Outputs per run:

- `changes.csv` (old -> new genre values)
- `unknown_genres.csv` (unknown value frequency + sample file)
- `genre_statistics.csv` (canonical genre counts)

### Loudness normalization with MP3Gain (MP3)

`MP3GainNormalizer` provides a large-library safe path for in-place MP3 loudness alignment:

1. filter supported files (`.mp3`)
2. run MP3Gain in track mode (`-r`) or album mode (`-a`)
3. apply clipping protection (`-k`) by default
4. process files in argument-length-safe chunks for Windows compatibility
5. on batch failure, retry per file to isolate damaged tracks

Safety characteristics:

- no audio re-encoding
- no container conversion
- per-file status results (updated/skipped/failed)
- configurable target offset relative to MP3Gain reference level (89 dB)

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

---

## Unsorted Sorting Helper

`unsorted_music_organizer.py` provides rule-based sorting used by the helper script under `scripts/`.

Behavior:

- scans an unsorted source folder recursively for supported audio files
- reads artist/album tags via mutagen
- checks existing artist folders in `D:\Musik\Interpreten` first
- creates artist folders only when the artist reaches a minimum track threshold
- checks existing album folders under the artist first
- creates album folders only when the album reaches a minimum track threshold

This allows gradual sorting without forcing one-off tracks into new artist folders too early.
