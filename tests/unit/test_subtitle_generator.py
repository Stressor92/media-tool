"""
tests/unit/test_subtitle_generator.py

Unit tests for SubtitleGenerator.
"""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch


from src.core.video import SubtitleGenerator


class TestSubtitleGenerator:
    """Test SubtitleGenerator functionality."""

    def create_test_video(self) -> Path:
        """Create a minimal test video file."""
        with tempfile.NamedTemporaryFile(suffix='.mkv', delete=False) as f:
            video_path = Path(f.name)
        # Write minimal MKV data (just for path existence)
        video_path.write_bytes(b'dummy mkv content')
        return video_path

    @patch('src.core.video.subtitle_generator.WhisperEngine')
    @patch('src.utils.audio_processor.extract_for_speech')
    @patch('src.core.video.subtitle_generator.SubtitleTimingProcessor')
    @patch('src.utils.ffmpeg_runner.FFmpegMuxer.add_subtitle_to_mkv')
    def test_generate_subtitles_success(self, mock_mux, mock_processor, mock_extract, mock_whisper):
        """Test successful subtitle generation."""
        # Setup mocks
        mock_extract.return_value = MagicMock(success=True, wav_path=Path("test.wav"), duration=60.0)
        mock_whisper.return_value.transcribe.return_value = MagicMock(
            success=True,
            srt_path=Path("test.srt"),
            hallucination_warnings=[]
        )
        mock_processor.return_value.sync_to_video.return_value = Path("test.srt")
        mock_processor.return_value.optimize_readability.return_value = Path("test.srt")
        mock_mux.return_value = MagicMock(success=True, output_file=Path("output.mkv"))

        generator = SubtitleGenerator()
        video_path = self.create_test_video()
        output_path = Path("output.mkv")

        try:
            result = generator.generate_subtitles(video_path, output_path)

            assert result.success
            assert result.output_mkv_path == output_path
            assert result.audio_duration == 60.0
            mock_extract.assert_called_once()
            mock_whisper.return_value.transcribe.assert_called_once()
            mock_processor.return_value.sync_to_video.assert_called_once()
            mock_processor.return_value.optimize_readability.assert_called_once()
            mock_mux.assert_called_once()
        finally:
            video_path.unlink()

    @patch('src.utils.audio_processor.extract_for_speech')
    def test_generate_subtitles_extract_fail(self, mock_extract):
        """Test subtitle generation when audio extraction fails."""
        mock_extract.return_value = MagicMock(success=False, error_message="Extract failed")

        generator = SubtitleGenerator()
        video_path = self.create_test_video()
        output_path = Path("output.mkv")

        try:
            result = generator.generate_subtitles(video_path, output_path)

            assert not result.success
            assert "Extract failed" in result.error_message
        finally:
            video_path.unlink()

    @patch('src.core.video.subtitle_generator.WhisperEngine')
    @patch('src.utils.audio_processor.extract_for_speech')
    def test_generate_subtitles_transcribe_fail(self, mock_extract, mock_whisper):
        """Test subtitle generation when transcription fails."""
        mock_extract.return_value = MagicMock(success=True, wav_path=Path("test.wav"), duration=60.0)
        mock_whisper.return_value.transcribe.return_value = MagicMock(
            success=False,
            error_message="Transcription failed"
        )

        generator = SubtitleGenerator()
        video_path = self.create_test_video()
        output_path = Path("output.mkv")

        try:
            result = generator.generate_subtitles(video_path, output_path)

            assert not result.success
            assert "Transcription failed" in result.error_message
        finally:
            video_path.unlink()

    @patch('src.core.video.subtitle_generator.WhisperEngine')
    @patch('src.utils.audio_processor.extract_for_speech')
    @patch('src.utils.ffmpeg_runner.FFmpegMuxer.add_subtitle_to_mkv')
    def test_generate_subtitles_mux_fail(self, mock_mux, mock_extract, mock_whisper):
        """Test subtitle generation when muxing fails."""
        mock_extract.return_value = MagicMock(success=True, wav_path=Path("test.wav"), duration=60.0)
        mock_whisper.return_value.transcribe.return_value = MagicMock(
            success=True,
            srt_path=Path("test.srt"),
            hallucination_warnings=[]
        )
        mock_mux.return_value = MagicMock(success=False, error_message="Mux failed")

        generator = SubtitleGenerator()
        video_path = self.create_test_video()
        output_path = Path("output.mkv")

        try:
            result = generator.generate_subtitles(video_path, output_path)

            assert not result.success
            assert "Mux failed" in result.error_message
        finally:
            video_path.unlink()

    @patch('src.core.video.subtitle_generator.WhisperEngine')
    @patch('src.utils.audio_processor.extract_for_speech')
    @patch('src.core.video.subtitle_generator.SubtitleTimingProcessor')
    @patch('src.utils.ffmpeg_runner.FFmpegMuxer.add_subtitle_to_mkv')
    def test_generate_subtitles_with_warnings(self, mock_mux, mock_processor, mock_extract, mock_whisper):
        """Test subtitle generation with hallucination warnings."""
        warnings = [MagicMock(type="known_pattern", message="Warning")]
        mock_extract.return_value = MagicMock(success=True, wav_path=Path("test.wav"), duration=60.0)
        mock_whisper.return_value.transcribe.return_value = MagicMock(
            success=True,
            srt_path=Path("test.srt"),
            hallucination_warnings=warnings
        )
        mock_processor.return_value.sync_to_video.return_value = Path("test.srt")
        mock_processor.return_value.optimize_readability.return_value = Path("test.srt")
        mock_mux.return_value = MagicMock(success=True, output_file=Path("output.mkv"))

        generator = SubtitleGenerator()
        video_path = self.create_test_video()
        output_path = Path("output.mkv")

        try:
            result = generator.generate_subtitles(video_path, output_path)

            assert result.success
            assert result.hallucination_warnings == warnings
        finally:
            video_path.unlink()