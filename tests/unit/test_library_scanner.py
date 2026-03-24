from __future__ import annotations

from pathlib import Path

from core.audio.library_scanner import LibraryScanner
from core.audio.metadata_extractor import AudioFileMetadata


class StubExtractor:
    def extract(self, file_path: Path) -> AudioFileMetadata:
        return AudioFileMetadata(
            file_path=file_path.resolve(),
            file_name=file_path.name,
            file_size_mb=1.0,
            directory=str(file_path.parent.resolve()),
            extension=file_path.suffix.lower().lstrip("."),
            duration_seconds=60.0,
        )


def test_scan_finds_supported_audio_files_only(tmp_path: Path) -> None:
    (tmp_path / "artist1").mkdir()
    (tmp_path / "artist1" / "song1.mp3").write_bytes(b"1")
    (tmp_path / "artist1" / "song2.flac").write_bytes(b"2")
    (tmp_path / "artist2").mkdir()
    (tmp_path / "artist2" / "song3.m4a").write_bytes(b"3")
    (tmp_path / "ignore.txt").write_text("ignore", encoding="utf-8")

    scanner = LibraryScanner(metadata_extractor=StubExtractor())
    results = scanner.scan(tmp_path)

    assert len(results) == 3
    assert [item.extension for item in results] == ["mp3", "flac", "m4a"]


def test_scan_reports_progress_for_each_processed_file(tmp_path: Path) -> None:
    for index in range(5):
        (tmp_path / f"song{index}.mp3").write_bytes(b"x")

    calls: list[tuple[int, int]] = []

    scanner = LibraryScanner(metadata_extractor=StubExtractor(), max_workers=2)
    scanner.scan(tmp_path, progress_callback=lambda current, total: calls.append((current, total)))

    assert len(calls) == 5
    assert calls[-1] == (5, 5)


def test_find_audio_files_respects_non_recursive_mode(tmp_path: Path) -> None:
    (tmp_path / "song1.mp3").write_bytes(b"1")
    (tmp_path / "nested").mkdir()
    (tmp_path / "nested" / "song2.mp3").write_bytes(b"2")

    scanner = LibraryScanner(metadata_extractor=StubExtractor())

    results = scanner.find_audio_files(tmp_path, recursive=False)

    assert results == [tmp_path / "song1.mp3"]
