from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from core.audio.metadata_extractor import AudioFileMetadata, MetadataExtractor
from utils.audio_analyzer import AudioTechnicalMetadata


class FakeEasyAudio(dict):
    tags = None


class FakeRawTags(dict):
    pass


class FakeRawAudio:
    def __init__(self, tags: dict[str, object], pictures: list[object] | None = None):
        self.tags = FakeRawTags(tags)
        self.pictures = pictures or []


def test_extract_metadata_populates_expected_fields(tmp_path: Path) -> None:
    audio_file = tmp_path / "track.mp3"
    audio_file.write_bytes(b"fake-audio")

    easy_audio = FakeEasyAudio(
        {
            "artist": ["Test Artist"],
            "album": ["Test Album"],
            "title": ["Test Song"],
            "albumartist": ["Test Album Artist"],
            "tracknumber": ["3/12"],
            "discnumber": ["1/2"],
            "date": ["2024-02-03"],
            "genre": ["Rock"],
            "comment": ["Test comment"],
        }
    )
    raw_audio = FakeRawAudio({}, pictures=[object()])

    extractor = MetadataExtractor()

    with patch.object(extractor, "_extract_technical_specs", return_value=AudioTechnicalMetadata(
        duration_seconds=245.12,
        codec="mp3",
        bitrate_kbps=320,
        sample_rate_hz=44100,
        channels=2,
        bit_depth=None,
    )):
        with patch("mutagen.File", side_effect=[easy_audio, raw_audio]):
            metadata = extractor.extract(audio_file)

    assert metadata.file_name == "track.mp3"
    assert metadata.extension == "mp3"
    assert metadata.artist == "Test Artist"
    assert metadata.album == "Test Album"
    assert metadata.title == "Test Song"
    assert metadata.album_artist == "Test Album Artist"
    assert metadata.track_number == "3"
    assert metadata.total_tracks == 12
    assert metadata.disc_number == 1
    assert metadata.year == 2024
    assert metadata.genre == "Rock"
    assert metadata.comment == "Test comment"
    assert metadata.codec == "mp3"
    assert metadata.bitrate_kbps == 320
    assert metadata.sample_rate_hz == 44100
    assert metadata.channels == 2
    assert metadata.is_tagged is True
    assert metadata.is_lossless is False
    assert metadata.has_cover_art is True


def test_extract_metadata_detects_lossless_format_from_codec(tmp_path: Path) -> None:
    audio_file = tmp_path / "track.m4a"
    audio_file.write_bytes(b"fake-audio")

    extractor = MetadataExtractor()

    with patch.object(extractor, "_extract_tags", return_value={}):
        with patch.object(extractor, "_extract_technical_specs", return_value=AudioTechnicalMetadata(codec="alac", duration_seconds=120.0)):
            metadata = extractor.extract(audio_file)

    assert metadata.is_lossless is True
    assert metadata.duration_seconds == 120.0


def test_extract_metadata_returns_error_entry_on_failure(tmp_path: Path) -> None:
    invalid_file = tmp_path / "invalid.mp3"
    invalid_file.write_bytes(b"broken")

    extractor = MetadataExtractor()

    with patch.object(extractor, "_extract_tags", side_effect=RuntimeError("bad tags")):
        metadata = extractor.extract(invalid_file)

    assert isinstance(metadata, AudioFileMetadata)
    assert metadata.error_message == "bad tags"
    assert metadata.file_name == "invalid.mp3"
