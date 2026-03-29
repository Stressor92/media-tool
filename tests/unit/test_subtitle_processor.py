"""
tests/unit/test_subtitle_processor.py

Unit tests for SubtitleTimingProcessor.
"""

import tempfile
from pathlib import Path


from core.video import SubtitleTimingProcessor


class TestSubtitleTimingProcessor:
    """Test SubtitleTimingProcessor functionality."""

    def test_sync_to_video(self):
        """Test subtitle syncing to video timeline."""
        processor = SubtitleTimingProcessor()

        # Create test SRT
        srt_content = """
1
00:00:00,000 --> 00:00:05,000
First subtitle

2
00:00:05,000 --> 00:00:10,000
Second subtitle
"""

        with tempfile.NamedTemporaryFile(mode='w', suffix='.srt', delete=False) as f:
            f.write(srt_content)
            input_srt = Path(f.name)

        try:
            result = processor.sync_to_video(input_srt, video_duration=15.0, wav_duration=10.0)

            # Should return a success result
            assert result.success
            assert isinstance(result.srt_path, Path)
            assert result.srt_path.exists()
        finally:
            input_srt.unlink()
            if result.srt_path and result.srt_path.exists():
                result.srt_path.unlink()

    def test_optimize_readability(self):
        """Test subtitle readability optimization."""
        processor = SubtitleTimingProcessor()

        # Create test SRT with short timings
        srt_content = """
1
00:00:00,000 --> 00:00:01,000
Very short subtitle

2
00:00:01,000 --> 00:00:02,000
Another short one
"""

        with tempfile.NamedTemporaryFile(mode='w', suffix='.srt', delete=False) as f:
            f.write(srt_content)
            input_srt = Path(f.name)

        try:
            output_srt = processor.optimize_readability(input_srt)

            assert isinstance(output_srt, Path)
            assert output_srt.exists()

            # Read optimized content
            with open(output_srt, 'r', encoding='utf-8') as f:
                optimized_content = f.read()

            # Should still have subtitles
            assert "Very short subtitle" in optimized_content
        finally:
            input_srt.unlink()
            if output_srt.exists():
                output_srt.unlink()

    def test_validate_srt_valid(self):
        """Test SRT validation with valid file."""
        processor = SubtitleTimingProcessor()

        srt_content = """
1
00:00:00,000 --> 00:00:05,000
Valid subtitle

2
00:00:05,000 --> 00:00:10,000
Another valid subtitle
"""

        with tempfile.NamedTemporaryFile(mode='w', suffix='.srt', delete=False) as f:
            f.write(srt_content)
            srt_path = Path(f.name)

        try:
            result = processor.validate_srt(srt_path)
            assert result.is_valid
            assert len(result.errors) == 0
        finally:
            srt_path.unlink()

    def test_validate_srt_invalid_timestamps(self):
        """Test SRT validation with invalid timestamps."""
        processor = SubtitleTimingProcessor()

        srt_content = """
1
00:00:10,000 --> 00:00:05,000
Invalid: end before start

2
00:00:05,000 --> 00:00:10,000
Valid subtitle
"""

        with tempfile.NamedTemporaryFile(mode='w', suffix='.srt', delete=False) as f:
            f.write(srt_content)
            srt_path = Path(f.name)

        try:
            result = processor.validate_srt(srt_path)
            assert not result.is_valid
            assert len(result.errors) > 0
            assert any("End time is before start time" in error for error in result.errors)
        finally:
            srt_path.unlink()

    def test_validate_srt_overlapping(self):
        """Test SRT validation with overlapping subtitles."""
        processor = SubtitleTimingProcessor()

        srt_content = """
1
00:00:00,000 --> 00:00:07,000
First subtitle

2
00:00:05,000 --> 00:00:10,000
Overlapping subtitle
"""

        with tempfile.NamedTemporaryFile(mode='w', suffix='.srt', delete=False) as f:
            f.write(srt_content)
            srt_path = Path(f.name)

        try:
            result = processor.validate_srt(srt_path)
            # Overlapping timestamps are treated as non-fatal warnings, not errors,
            # because fix_overlapping_timestamps() is always called before validate_srt()
            # in production. The file is still usable.
            assert result.is_valid
            assert len(result.warnings) > 0
            assert any("overlap" in w.lower() for w in result.warnings)
        finally:
            srt_path.unlink()