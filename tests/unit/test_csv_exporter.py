from __future__ import annotations

import csv
from datetime import UTC, datetime
from pathlib import Path

from core.audio.csv_exporter import CSVExporter
from core.audio.metadata_extractor import AudioFileMetadata


def test_csv_export_writes_expected_columns_and_values(tmp_path: Path) -> None:
    metadata = AudioFileMetadata(
        file_path=tmp_path / "track.flac",
        file_name="track.flac",
        file_size_mb=12.34,
        directory=str(tmp_path),
        extension="flac",
        duration_seconds=245.67,
        artist="Artist",
        album="Album",
        title="Title",
        album_artist="Album Artist",
        track_number="3",
        total_tracks=12,
        disc_number=1,
        year=2024,
        genre="Jazz",
        comment="Note",
        codec="flac",
        bitrate_kbps=900,
        sample_rate_hz=96000,
        channels=2,
        bit_depth=24,
        is_lossless=True,
        is_tagged=True,
        has_cover_art=False,
        date_modified=datetime(2024, 1, 2, tzinfo=UTC),
        date_scanned=datetime(2024, 1, 3, tzinfo=UTC),
    )

    exporter = CSVExporter()
    output_path = tmp_path / "library.csv"

    rows_written = exporter.export([metadata], output_path)

    assert rows_written == 1
    with output_path.open("r", encoding="utf-8-sig", newline="") as handle:
        row = next(csv.DictReader(handle))

    assert row["file_name"] == "track.flac"
    assert row["file_size_mb"] == "12.34"
    assert row["duration_seconds"] == "245.67"
    assert row["is_lossless"] == "true"
    assert row["has_cover_art"] == "false"
    assert row["bit_depth"] == "24"


def test_csv_export_can_exclude_error_rows(tmp_path: Path) -> None:
    exporter = CSVExporter()
    output_path = tmp_path / "library.csv"

    ok_row = AudioFileMetadata(
        file_path=tmp_path / "ok.mp3",
        file_name="ok.mp3",
        file_size_mb=1.0,
        directory=str(tmp_path),
        extension="mp3",
        duration_seconds=10.0,
    )
    error_row = AudioFileMetadata(
        file_path=tmp_path / "broken.mp3",
        file_name="broken.mp3",
        file_size_mb=1.0,
        directory=str(tmp_path),
        extension="mp3",
        duration_seconds=0.0,
        error_message="bad file",
    )

    rows_written = exporter.export([ok_row, error_row], output_path, include_errors=False)

    assert rows_written == 1
    with output_path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 1
    assert rows[0]["file_name"] == "ok.mp3"
