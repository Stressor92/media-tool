"""Unit tests for download format selector logic."""

from pathlib import Path
from typing import Any

from core.download.format_selector import build_format_string, build_postprocessors
from core.download.models import DownloadRequest, MediaType


def _make_request(media_type: MediaType, **kwargs: object) -> DownloadRequest:
    defaults: dict[str, Any] = {
        "url": "https://example.com",
        "media_type": media_type,
        "output_dir": Path("out"),
    }
    defaults.update(kwargs)
    return DownloadRequest(**defaults)


class TestBuildFormatString:
    def test_music_uses_bestaudio(self) -> None:
        value = build_format_string(_make_request(MediaType.MUSIC))
        assert value == "bestaudio/best"

    def test_video_contains_resolution(self) -> None:
        value = build_format_string(_make_request(MediaType.VIDEO, max_resolution=720))
        assert "bestvideo" in value
        assert "720" in value

    def test_series_contains_resolution(self) -> None:
        value = build_format_string(_make_request(MediaType.SERIES, max_resolution=480))
        assert "480" in value


class TestBuildPostprocessors:
    def test_music_has_audio_extraction(self) -> None:
        processors = build_postprocessors(_make_request(MediaType.MUSIC))
        keys = [entry["key"] for entry in processors]
        assert "FFmpegExtractAudio" in keys

    def test_video_embeds_subtitles_when_enabled(self) -> None:
        processors = build_postprocessors(_make_request(MediaType.VIDEO, embed_subtitles=True))
        keys = [entry["key"] for entry in processors]
        assert "FFmpegEmbedSubtitle" in keys

    def test_video_omits_subtitles_when_disabled(self) -> None:
        processors = build_postprocessors(_make_request(MediaType.VIDEO, embed_subtitles=False))
        keys = [entry["key"] for entry in processors]
        assert "FFmpegEmbedSubtitle" not in keys

    def test_sponsorblock_removed_when_empty(self) -> None:
        processors = build_postprocessors(_make_request(MediaType.VIDEO, sponsorblock_remove=()))
        keys = [entry["key"] for entry in processors]
        assert "SponsorBlock" not in keys

    def test_music_audio_codec_forwarded(self) -> None:
        processors = build_postprocessors(_make_request(MediaType.MUSIC, audio_format="flac"))
        extract = next(item for item in processors if item["key"] == "FFmpegExtractAudio")
        assert extract["preferredcodec"] == "flac"
