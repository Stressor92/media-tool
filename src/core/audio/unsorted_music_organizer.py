"""Rule-based organizer for tracks from an unsorted import folder."""

from __future__ import annotations

import shutil
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mutagen import File as mutagen_file

AUDIO_EXTENSIONS = {".mp3", ".flac", ".m4a", ".aac", ".ogg", ".wma", ".wav", ".opus"}
INVALID_FILENAME_CHARS = '<>:"/\\|?*'


@dataclass(frozen=True)
class TrackRecord:
    """Extracted metadata for one source track."""

    source_path: Path
    artist: str | None
    album: str | None


@dataclass
class SortSummary:
    """Result counters for unsorted-track organization."""

    scanned_tracks: int = 0
    moved_tracks: int = 0
    moved_to_artist: int = 0
    moved_to_album: int = 0
    skipped_missing_artist: int = 0
    skipped_no_target: int = 0
    skipped_duplicate_target: int = 0
    errors: int = 0


def sanitize_path_component(value: str) -> str:
    """Sanitize artist/album folder names for Windows file systems."""
    sanitized = value
    for char in INVALID_FILENAME_CHARS:
        sanitized = sanitized.replace(char, "_")
    sanitized = sanitized.strip().rstrip(".")
    return sanitized or "Unknown"


def normalize_key(value: str) -> str:
    """Normalize text for case-insensitive comparisons."""
    return " ".join(value.casefold().split())


def _is_audio_file(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in AUDIO_EXTENSIONS


def _extract_mapping_value(mapping: Any, keys: list[str]) -> str | None:
    getter = getattr(mapping, "get", None)
    if not callable(getter):
        return None

    for key in keys:
        raw = getter(key)
        if isinstance(raw, list | tuple):
            if not raw:
                continue
            raw = raw[0]
        if raw is None:
            continue
        value = str(raw).strip()
        if value:
            return value
    return None


def extract_artist_album(track_path: Path) -> tuple[str | None, str | None]:
    """Read artist/album metadata from mutagen tags."""
    try:
        audio = mutagen_file(track_path, easy=True)
    except Exception:
        return None, None

    if audio is None:
        return None, None

    mapping = audio if callable(getattr(audio, "get", None)) else getattr(audio, "tags", None)
    if mapping is None:
        return None, None

    artist = _extract_mapping_value(mapping, ["artist", "albumartist", "author"])
    album = _extract_mapping_value(mapping, ["album"])
    return artist, album


def scan_unsorted_tracks(source_dir: Path) -> list[TrackRecord]:
    """Collect all supported audio tracks from the unsorted source directory."""
    records: list[TrackRecord] = []
    for path in source_dir.rglob("*"):
        if not _is_audio_file(path):
            continue
        artist, album = extract_artist_album(path)
        records.append(TrackRecord(source_path=path, artist=artist, album=album))
    return records


def _index_existing_artist_dirs(artists_root: Path) -> dict[str, Path]:
    if not artists_root.is_dir():
        return {}

    index: dict[str, Path] = {}
    for child in artists_root.iterdir():
        if child.is_dir():
            index.setdefault(normalize_key(child.name), child)
    return index


def _index_existing_album_dirs(artist_dir: Path) -> dict[str, Path]:
    if not artist_dir.is_dir():
        return {}

    index: dict[str, Path] = {}
    for child in artist_dir.iterdir():
        if child.is_dir():
            index.setdefault(normalize_key(child.name), child)
    return index


def _resolve_target_dir(
    record: TrackRecord,
    artists_root: Path,
    existing_artist_dirs: dict[str, Path],
    album_dir_cache: dict[Path, dict[str, Path]],
    artist_counts: Counter[str],
    album_counts: Counter[tuple[str, str]],
    min_artist_tracks: int,
    min_album_tracks: int,
) -> tuple[Path | None, str | None]:
    if not record.artist:
        return None, None

    artist_key = normalize_key(record.artist)
    artist_dir = existing_artist_dirs.get(artist_key)

    if artist_dir is None:
        if artist_counts[artist_key] < min_artist_tracks:
            return None, None
        artist_dir = artists_root / sanitize_path_component(record.artist)

    album_value = (record.album or "").strip()
    if not album_value:
        return artist_dir, "artist"

    album_key = normalize_key(album_value)
    existing_albums = album_dir_cache.setdefault(artist_dir, _index_existing_album_dirs(artist_dir))
    existing_album_dir = existing_albums.get(album_key)

    if existing_album_dir is not None:
        return existing_album_dir, "album"

    if album_counts[(artist_key, album_key)] >= min_album_tracks:
        return artist_dir / sanitize_path_component(album_value), "album"

    return artist_dir, "artist"


def _resolve_destination_path(source_file: Path, target_dir: Path) -> tuple[Path | None, bool]:
    """Return destination path and whether an identical duplicate already exists."""
    destination = target_dir / source_file.name
    if not destination.exists():
        return destination, False

    try:
        if source_file.stat().st_size == destination.stat().st_size:
            return None, True
    except OSError:
        pass

    counter = 1
    while True:
        candidate = target_dir / f"{source_file.stem} ({counter}){source_file.suffix}"
        if not candidate.exists():
            return candidate, False
        counter += 1


def organize_unsorted_music(
    source_dir: Path,
    artists_root: Path,
    min_artist_tracks: int = 5,
    min_album_tracks: int = 5,
    dry_run: bool = False,
) -> SortSummary:
    """Move tracks from an unsorted folder into artist/album structure.

    Rules:
    - Existing artist folders in artists_root have priority.
    - Otherwise, artist folder is created when at least min_artist_tracks exist.
    - Existing album folders in artist folder have priority.
    - Otherwise, album folder is created when at least min_album_tracks exist.
    """
    if min_artist_tracks < 1:
        raise ValueError("min_artist_tracks must be >= 1")
    if min_album_tracks < 1:
        raise ValueError("min_album_tracks must be >= 1")
    if not source_dir.is_dir():
        raise NotADirectoryError(f"Source directory not found: {source_dir}")

    if not dry_run:
        artists_root.mkdir(parents=True, exist_ok=True)

    records = scan_unsorted_tracks(source_dir)
    summary = SortSummary(scanned_tracks=len(records))

    artist_counts = Counter(normalize_key(record.artist) for record in records if record.artist)
    album_counts = Counter(
        (normalize_key(record.artist), normalize_key(record.album))
        for record in records
        if record.artist and record.album
    )

    existing_artist_dirs = _index_existing_artist_dirs(artists_root)
    album_dir_cache: dict[Path, dict[str, Path]] = {}

    for record in records:
        if not record.artist:
            summary.skipped_missing_artist += 1
            continue

        target_dir, target_kind = _resolve_target_dir(
            record=record,
            artists_root=artists_root,
            existing_artist_dirs=existing_artist_dirs,
            album_dir_cache=album_dir_cache,
            artist_counts=artist_counts,
            album_counts=album_counts,
            min_artist_tracks=min_artist_tracks,
            min_album_tracks=min_album_tracks,
        )

        if target_dir is None or target_kind is None:
            summary.skipped_no_target += 1
            continue

        destination, is_duplicate = _resolve_destination_path(record.source_path, target_dir)
        if is_duplicate:
            summary.skipped_duplicate_target += 1
            continue
        if destination is None:
            summary.errors += 1
            continue

        try:
            if not dry_run:
                target_dir.mkdir(parents=True, exist_ok=True)
                shutil.move(str(record.source_path), str(destination))
            summary.moved_tracks += 1
            if target_kind == "album":
                summary.moved_to_album += 1
            else:
                summary.moved_to_artist += 1
        except Exception:
            summary.errors += 1

    return summary
