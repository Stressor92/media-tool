# tests/integration/test_translation_integration.py
"""
Integration tests for the subtitle translation module.

Requires: MEDIA_TOOL_LIVE_INTEGRATION_TESTS=1
          pip install ctranslate2 transformers sentencepiece
          (Model is downloaded automatically on first run)
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from core.translation.models import LanguagePair, TranslationStatus
from core.translation.subtitle_translator import SubtitleTranslator

_EN_SRT = """\
1
00:00:01,000 --> 00:00:03,000
Good morning.

2
00:00:04,000 --> 00:00:06,000
How are you today?

3
00:00:07,000 --> 00:00:09,000
The weather is beautiful.

"""

_DE_SRT = """\
1
00:00:01,000 --> 00:00:03,000
Guten Morgen.

2
00:00:04,000 --> 00:00:06,000
Wie geht es Ihnen heute?

3
00:00:07,000 --> 00:00:09,000
Das Wetter ist wunderschön.

"""

pytestmark = [
    pytest.mark.integration,
    pytest.mark.external,
    pytest.mark.live_integration,
    pytest.mark.skipif(
        os.environ.get("MEDIA_TOOL_LIVE_INTEGRATION_TESTS") != "1",
        reason="Set MEDIA_TOOL_LIVE_INTEGRATION_TESTS=1 to run translation integration tests",
    ),
]


class TestOpusMtIntegration:
    def test_en_to_de_translation(self, tmp_path: Path) -> None:
        src = tmp_path / "test.en.srt"
        src.write_text(_EN_SRT)

        st = SubtitleTranslator()
        result = st.translate_file(
            source_path=src,
            language_pair=LanguagePair.en_to_de(),
            backend="opus-mt",
            model_size="standard",  # Standard for faster test
        )

        assert result.status == TranslationStatus.SUCCESS
        assert result.output_path is not None
        content = result.output_path.read_text()

        # Basic plausibility — not exact wording
        assert "morgen" in content.lower() or "guten" in content.lower()
        assert result.segments_translated == 3

    def test_de_to_en_translation(self, tmp_path: Path) -> None:
        src = tmp_path / "test.de.srt"
        src.write_text(_DE_SRT)

        st = SubtitleTranslator()
        result = st.translate_file(
            source_path=src,
            language_pair=LanguagePair.de_to_en(),
            backend="opus-mt",
            model_size="standard",
        )

        assert result.status == TranslationStatus.SUCCESS
        content = result.output_path.read_text()  # type: ignore[union-attr]
        assert "morning" in content.lower() or "good" in content.lower()

    def test_vtt_format_preserved(self, tmp_path: Path) -> None:
        src = tmp_path / "test.en.vtt"
        src.write_text("WEBVTT\n\n00:00:01.000 --> 00:00:03.000\nHello.\n\n")

        st = SubtitleTranslator()
        result = st.translate_file(
            src,
            LanguagePair.en_to_de(),
            backend="opus-mt",
            model_size="standard",
        )

        assert result.status == TranslationStatus.SUCCESS
        assert result.output_path is not None
        assert result.output_path.suffix == ".vtt"

    def test_output_path_naming(self, tmp_path: Path) -> None:
        src = tmp_path / "movie.en.srt"
        src.write_text(_EN_SRT)

        st = SubtitleTranslator()
        result = st.translate_file(src, LanguagePair.en_to_de(), backend="opus-mt", model_size="standard")

        assert result.output_path is not None
        assert result.output_path.name == "movie.de.srt"

    def test_performance_benchmark(self, tmp_path: Path) -> None:
        """500 segments should be translated in under 60 seconds."""
        segments = "\n\n".join(
            f"{i}\n00:0{i // 60:02d}:{i % 60:02d},000 --> 00:0{i // 60:02d}:{(i % 60) + 1:02d},000\n"
            f"This is sentence number {i}."
            for i in range(1, 501)
        )
        src = tmp_path / "long.en.srt"
        src.write_text(segments)

        st = SubtitleTranslator()
        result = st.translate_file(
            src,
            LanguagePair.en_to_de(),
            backend="opus-mt",
            model_size="standard",
        )

        assert result.status == TranslationStatus.SUCCESS
        assert result.duration_seconds < 60.0
        assert result.segments_translated == 500
