"""
tests/integration/test_subtitle_pipeline.py

Integration tests for the complete subtitle generation pipeline.
"""

import tempfile
import wave
from pathlib import Path
from unittest.mock import patch


from core.video import SubtitleGenerator, WhisperConfig


class TestSubtitlePipeline:
    """Integration tests for subtitle generation pipeline."""

    def create_test_video(self) -> Path:
        """Create a minimal test video file (actually just a dummy file for path)."""
        with tempfile.NamedTemporaryFile(suffix='.mkv', delete=False) as f:
            video_path = Path(f.name)
        # Write minimal content to make it exist
        video_path.write_bytes(b'dummy mkv content for testing')
        return video_path

    def create_test_wav(self, duration_seconds: float = 10.0) -> Path:
        """Create a minimal test WAV file."""
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            wav_path = Path(f.name)

        # Create a simple WAV file
        with wave.open(str(wav_path), 'wb') as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(16000)
            # Write minimal data
            frames = b'\x00\x00' * int(16000 * duration_seconds)
            wav.writeframes(frames)

        return wav_path

    @patch('core.video.whisper_engine.WhisperEngine._run_whisper')
    @patch('utils.audio_processor.extract_for_speech')
    @patch('core.video.subtitle_processor.SubtitleTimingProcessor.sync_to_video')
    @patch('core.video.subtitle_processor.SubtitleTimingProcessor.optimize_readability')
    @patch('utils.ffmpeg_runner.FFmpegMuxer.add_subtitle_to_mkv')
    def test_full_pipeline_success(
        self, mock_mux, mock_optimize, mock_sync, mock_extract, mock_run_whisper
    ):
        """Test the complete subtitle generation pipeline."""
        # Setup mocks
        mock_extract.return_value = type('MockResult', (), {
            'success': True,
            'wav_path': self.create_test_wav(10.0),
            'duration': 10.0
        })()

        # Create a dummy SRT file for the mock
        srt_path = Path(tempfile.mktemp(suffix='.srt'))
        srt_path.write_text("""
1
00:00:00,000 --> 00:00:05,000
Hello world

2
00:00:05,000 --> 00:00:10,000
This is a test
""")

        mock_run_whisper.return_value = None  # Just succeed

        mock_sync.return_value = srt_path
        mock_optimize.return_value = srt_path
        mock_mux.return_value = type('MockResult', (), {
            'success': True,
            'output_file': Path('output.mkv')
        })()

        # Run the pipeline
        generator = SubtitleGenerator()
        video_path = self.create_test_video()
        output_path = Path(tempfile.mktemp(suffix='.mkv'))

        try:
            result = generator.generate_subtitles(video_path, output_path)

            assert result.success
            assert result.output_mkv_path == output_path
            assert result.audio_duration == 10.0
            assert result.processing_time > 0

            # Verify calls
            mock_extract.assert_called_once()
            mock_run_whisper.assert_called_once()
            mock_sync.assert_called_once()
            mock_optimize.assert_called_once()
            mock_mux.assert_called_once()

        finally:
            video_path.unlink()
            srt_path.unlink()
            if output_path.exists():
                output_path.unlink()

    @patch('utils.audio_processor.extract_for_speech')
    def test_pipeline_audio_extraction_failure(self, mock_extract):
        """Test pipeline failure at audio extraction."""
        mock_extract.return_value = type('MockResult', (), {
            'success': False,
            'error_message': 'Audio extraction failed'
        })()

        generator = SubtitleGenerator()
        video_path = self.create_test_video()
        output_path = Path(tempfile.mktemp(suffix='.mkv'))

        try:
            result = generator.generate_subtitles(video_path, output_path)

            assert not result.success
            assert 'Audio extraction failed' in result.error_message

        finally:
            video_path.unlink()

    @patch('core.video.whisper_engine.WhisperEngine._run_whisper')
    @patch('utils.audio_processor.extract_for_speech')
    @patch('utils.ffmpeg_runner.FFmpegMuxer.add_subtitle_to_mkv')
    def test_pipeline_mux_failure(self, mock_mux, mock_extract, mock_run_whisper):
        """Test pipeline failure at muxing."""
        mock_extract.return_value = type('MockResult', (), {
            'success': True,
            'wav_path': self.create_test_wav(10.0),
            'duration': 10.0
        })()

        srt_path = Path(tempfile.mktemp(suffix='.srt'))
        srt_path.write_text("dummy srt")
        mock_run_whisper.return_value = None

        mock_mux.return_value = type('MockResult', (), {
            'success': False,
            'error_message': 'Muxing failed'
        })()

        generator = SubtitleGenerator()
        video_path = self.create_test_video()
        output_path = Path(tempfile.mktemp(suffix='.mkv'))

        try:
            result = generator.generate_subtitles(video_path, output_path)

            assert not result.success
            assert 'Muxing failed' in result.error_message

        finally:
            video_path.unlink()
            srt_path.unlink()

    def test_pipeline_with_hallucination_warnings(self):
        """Test pipeline with hallucination detection enabled."""
        # This would require more complex mocking of the whisper engine
        # For now, just ensure the config is passed correctly
        config = WhisperConfig(language="de", model="small")
        generator = SubtitleGenerator(config)

        assert generator.whisper_config.language == "de"
        assert generator.whisper_config.model.value == "small"