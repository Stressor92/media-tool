from __future__ import annotations

import csv
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import pytest
from mutagen.easyid3 import EasyID3
from mutagen.flac import FLAC
from mutagen.mp3 import MP3

from core.audio.csv_exporter import CSVExporter
from core.audio.library_scanner import LibraryScanner
from core.audio.metadata_extractor import MetadataExtractor


def _tag_mp3(file_path: Path, *, artist: str, album: str, title: str, tracknumber: str) -> None:
    audio = MP3(file_path, ID3=EasyID3)
    try:
        add_tags = cast(Callable[[], None], audio.add_tags)
        add_tags()
    except Exception:
        pass
    audio["artist"] = [artist]
    audio["album"] = [album]
    audio["title"] = [title]
    audio["tracknumber"] = [tracknumber]
    audio.save()


def _tag_flac(file_path: Path, *, artist: str, album: str, title: str, tracknumber: str) -> None:
    audio = FLAC(file_path)
    audio["artist"] = artist
    audio["album"] = album
    audio["title"] = title
    audio["tracknumber"] = tracknumber
    audio.save()


@pytest.mark.integration
def test_complete_scan_workflow(tmp_path: Path, media_generator: Any) -> None:
    library_root = tmp_path / "library"
    album_one = library_root / "Artist1" / "Album1"
    album_two = library_root / "Artist2" / "Album2"
    album_one.mkdir(parents=True)
    album_two.mkdir(parents=True)

    song1 = media_generator.create_test_audio(album_one / "01 - Song1.mp3", duration=2.0, sample_rate=44100)
    song2 = media_generator.create_test_audio(album_one / "02 - Song2.mp3", duration=2.0, sample_rate=44100)
    song3 = media_generator.create_test_audio(album_two / "01 - Song3.flac", duration=2.0, sample_rate=48000)

    _tag_mp3(song1, artist="Artist1", album="Album1", title="Song1", tracknumber="1/2")
    _tag_mp3(song2, artist="Artist1", album="Album1", title="Song2", tracknumber="2/2")
    _tag_flac(song3, artist="Artist2", album="Album2", title="Song3", tracknumber="1/1")

    scanner = LibraryScanner(metadata_extractor=MetadataExtractor(), max_workers=2)
    exporter = CSVExporter()

    results = scanner.scan(library_root)

    assert len(results) == 3
    assert all(not item.error_message for item in results)
    assert {item.artist for item in results} == {"Artist1", "Artist2"}
    assert any(item.is_lossless for item in results)

    output_path = tmp_path / "library.csv"
    rows_written = exporter.export(results, output_path)

    assert rows_written == 3
    with output_path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))

    assert len(rows) == 3
    assert all("artist" in row for row in rows)
    assert all("bitrate_kbps" in row for row in rows)
    assert {row["file_name"] for row in rows} == {"01 - Song1.mp3", "02 - Song2.mp3", "01 - Song3.flac"}
