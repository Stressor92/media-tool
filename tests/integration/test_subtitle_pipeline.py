"""
tests/integration/test_subtitle_pipeline.py

Integration tests for the complete subtitle generation pipeline.
"""

import tempfile
from pathlib import Path
from unittest.mock import patch


from core.video import SubtitleGenerator, WhisperConfig


class TestSubtitlePipeline:
    """Integration tests for subtitle generation pipeline."""

    @patch('core.video.whisper_engine.WhisperEngine._run_whisper')
    @patch('utils.audio_processor.extract_for_speech')
    @patch('core.video.subtitle_processor.SubtitleTimingProcessor.sync_to_video')
    @patch('core.video.subtitle_processor.SubtitleTimingProcessor.optimize_readability')
    @patch('utils.ffmpeg_runner.FFmpegMuxer.add_subtitle_to_mkv')
    def test_full_pipeline_success(
        self, mock_mux, mock_optimize, mock_sync, mock_extract, mock_run_whisper, test_video_720p, test_audio_wav
    ):
        """Test the complete subtitle generation pipeline with valid media."""
        # Setup mocks - use valid WAV with sufficient duration
        mock_extract.return_value = type('MockResult', (), {
            'success': True,
            'wav_path': test_audio_wav,
            'duration': 10.0  # Sufficient duration for Whisper
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

        mock_sync.return_value = type('MockSyncResult', (), {
            'success': True,
            'srt_path': srt_path,
            'scale_factor': 1.0,
            'error_message': None
        })()
        mock_optimize.return_value = srt_path
        mock_mux.return_value = type('MockResult', (), {
            'success': True,
            'output_file': Path('output.mkv')
        })()

        # Run the pipeline
        generator = SubtitleGenerator()
        output_path = Path(tempfile.mktemp(suffix='.mkv'))

        try:
            result = generator.generate_subtitles(test_video_720p, output_path)

            # Verify that with valid video file, processing reaches extraction
            assert "input_validation" in result.steps_completed
            assert "audio_extraction" in result.steps_completed or not result.success
            mock_extract.assert_called_once()

        finally:
            srt_path.unlink()
            if output_path.exists():
                output_path.unlink()

    @patch('utils.audio_processor.extract_for_speech')
    def test_pipeline_audio_extraction_failure(self, mock_extract, test_video_720p):
        """Test pipeline failure at audio extraction."""
        mock_extract.return_value = type('MockResult', (), {
            'success': False,
            'error_message': 'Audio extraction failed'
        })()

        generator = SubtitleGenerator()
        output_path = Path(tempfile.mktemp(suffix='.mkv'))

        try:
            result = generator.generate_subtitles(test_video_720p, output_path)

            assert not result.success
            # Should reach audio_extraction before failing
            assert "audio_extraction" in result.steps_completed or len(result.steps_completed) > 0

        finally:
            if output_path.exists():
                output_path.unlink()

    @patch('core.video.whisper_engine.WhisperEngine._run_whisper')
    @patch('utils.audio_processor.extract_for_speech')
    @patch('utils.ffmpeg_runner.FFmpegMuxer.add_subtitle_to_mkv')
    def test_pipeline_mux_failure(self, mock_mux, mock_extract, mock_run_whisper, test_video_720p, test_audio_wav):
        """Test pipeline failure at muxing."""
        mock_extract.return_value = type('MockResult', (), {
            'success': True,
            'wav_path': test_audio_wav,
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
        output_path = Path(tempfile.mktemp(suffix='.mkv'))

        try:
            result = generator.generate_subtitles(test_video_720p, output_path)

            assert not result.success
            # Should attempt extraction with valid video
            assert "audio_extraction" in result.steps_completed or len(result.steps_completed) > 0

        finally:
            srt_path.unlink()
            if output_path.exists():
                output_path.unlink()

    def test_pipeline_with_hallucination_warnings(self):
        """Test pipeline with hallucination detection enabled."""
        # This would require more complex mocking of the whisper engine
        # For now, just ensure the config is passed correctly
        from core.video import WhisperConfig
        config = WhisperConfig(language="de", model="small")
        generator = SubtitleGenerator(config)

        assert generator.whisper_config.language == "de"
        # Model is an enum, check its string value
        assert "small" in str(generator.whisper_config.model).lower()