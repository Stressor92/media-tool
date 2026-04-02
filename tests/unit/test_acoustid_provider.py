"""tests/unit/test_acoustid_provider.py

Tests for AcoustID/MusicBrainz metadata provider and audio tagger workflow.
"""

from __future__ import annotations

from unittest.mock import patch

import acoustid
import musicbrainzngs
import pytest

from core.audio.audio_tagger import AudioTagger
from core.audio.metadata_providers.acoustid_provider import AcoustIDProvider
from core.audio.metadata_providers.provider import TrackMatch, TrackMetadata
from utils.chromaprint_runner import ChromaprintRunner
from utils.mutagen_tagger import MutagenTagger


def test_chromaprint_runner_missing_file(tmp_path):
    runner = ChromaprintRunner()
    missing = tmp_path / "missing.mp3"

    result = runner.calculate_fingerprint(missing)

    assert result.success is False
    assert "not found" in (result.error_message or "").lower()


def test_acoustid_provider_when_api_key_missing_raises():
    provider = AcoustIDProvider(acoustid_api_key="")

    with pytest.raises(ValueError):
        provider.lookup_by_fingerprint("abc", 1.0)


def test_acoustid_provider_lookup_by_fingerprint_acoustid_error():
    provider = AcoustIDProvider(acoustid_api_key="testkey")

    with patch("core.audio.metadata_providers.acoustid_provider.acoustid.lookup") as mock_lookup:
        mock_lookup.side_effect = acoustid.AcoustidError("network")

        with pytest.raises(RuntimeError):
            provider.lookup_by_fingerprint("abc", 1.0)


def test_acoustid_provider_lookup_by_fingerprint_status_not_ok():
    provider = AcoustIDProvider(acoustid_api_key="testkey")

    with patch("core.audio.metadata_providers.acoustid_provider.acoustid.lookup") as mock_lookup:
        mock_lookup.return_value = {"status": "error", "results": []}

        matches = provider.lookup_by_fingerprint("abc", 1.0)

        assert matches == []


def test_acoustid_provider_lookup_by_id_returns_metadata():
    provider = AcoustIDProvider(acoustid_api_key="testkey")

    fake_response = {
        "recording": {
            "title": "Test Song",
            "artist-credit": [{"artist": {"name": "Test Artist"}}],
            "release-list": [
                {
                    "title": "Test Album",
                    "medium-list": [
                        {
                            "position": "1",
                            "track-list": [{"number": "2"}],
                        }
                    ],
                }
            ],
        }
    }

    with patch("core.audio.metadata_providers.acoustid_provider.musicbrainzngs.get_recording_by_id") as mock_mb:
        mock_mb.return_value = fake_response

        metadata = provider.lookup_by_id("12345")

        assert metadata is not None
        assert metadata.title == "Test Song"
        assert metadata.artist == "Test Artist"
        assert metadata.album == "Test Album"
        assert metadata.track_number == 2
        assert metadata.disc_number == 1


def test_acoustid_provider_lookup_by_id_response_error_returns_none():
    provider = AcoustIDProvider(acoustid_api_key="testkey")

    with patch("core.audio.metadata_providers.acoustid_provider.musicbrainzngs.get_recording_by_id") as mock_mb:
        mock_mb.side_effect = musicbrainzngs.ResponseError("not found")

        metadata = provider.lookup_by_id("12345")

        assert metadata is None


def test_audio_tagger_auto_tag_success(tmp_path):
    audio_file = tmp_path / "track.mp3"
    audio_file.write_bytes(b"fake")

    fake_metadata = TrackMetadata(
        title="Test Song",
        artist="Test Artist",
        album="Test Album",
        musicbrainz_id="12345",
    )
    fake_match = TrackMatch(metadata=fake_metadata, confidence=0.95, source="acoustid")

    with patch.object(AcoustIDProvider, "from_audio_file", return_value=[fake_match]):
        with patch.object(MutagenTagger, "write_metadata") as mock_tag:
            tagger = AudioTagger(acoustid_api_key="testkey")
            applied = tagger.auto_tag(str(audio_file), force=True, min_confidence=0.8)

            assert applied is not None
            assert applied.title == "Test Song"
            mock_tag.assert_called_once_with(str(audio_file), fake_metadata, force=True)


def test_audio_tagger_auto_tag_no_match_returns_none(tmp_path):
    audio_file = tmp_path / "track.mp3"
    audio_file.write_bytes(b"fake")

    with patch.object(AcoustIDProvider, "from_audio_file", return_value=[]):
        tagger = AudioTagger(acoustid_api_key="testkey")
        result = tagger.auto_tag(str(audio_file), min_confidence=0.5)

        assert result is None
