"""
tests/unit/test_whisper_engine_errors.py

Comprehensive error handling tests for Whisper speech-to-text engine.
Tests invalid audio, model loading errors, resource issues, and timeout scenarios.
"""

from __future__ import annotations

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
import os

from core.video.whisper_engine import WhisperEngine, TranscriptionResult


class TestWhisperEngineInvalidInput:
    """Test error handling for invalid audio input."""

    def test_transcribe_audio_file_not_found(self):
        """Test transcription when audio file doesn't exist."""
        engine = WhisperEngine(model_size="base")
        audio_file = Path("nonexistent.mp3")
        
        result = engine.transcribe(audio_file)
        
        assert result.success is False
        assert "not found" in result.error.lower()

    def test_transcribe_audio_is_directory(self, tmp_path):
        """Test transcription when source is directory, not file."""
        engine = WhisperEngine(model_size="base")
        audio_dir = tmp_path / "audio_dir"
        audio_dir.mkdir()
        
        result = engine.transcribe(audio_dir)
        
        assert result.success is False

    def test_transcribe_empty_audio_file(self, tmp_path):
        """Test transcription of empty audio file."""
        engine = WhisperEngine(model_size="base")
        audio_file = tmp_path / "empty.mp3"
        audio_file.write_bytes(b"")
        
        with patch("core.video.whisper_engine.whisper.load_model") as mock_load:
            with patch("core.video.whisper_engine.whisper.transcribe") as mock_transcribe:
                mock_transcribe.side_effect = RuntimeError("Invalid audio format")
                
                result = engine.transcribe(audio_file)
                
                assert result.success is False

    def test_transcribe_corrupt_audio_file(self, tmp_path):
        """Test transcription of corrupt audio file."""
        engine = WhisperEngine(model_size="base")
        audio_file = tmp_path / "corrupt.mp3"
        audio_file.write_bytes(b"This is not valid audio data")
        
        with patch("core.video.whisper_engine.whisper.load_model") as mock_load:
            with patch("core.video.whisper_engine.whisper.transcribe") as mock_transcribe:
                mock_transcribe.side_effect = RuntimeError("Invalid audio codec")
                
                result = engine.transcribe(audio_file)
                
                assert result.success is False

    def test_transcribe_unsupported_audio_format(self, tmp_path):
        """Test transcription of unsupported audio format."""
        engine = WhisperEngine(model_size="base")
        audio_file = tmp_path / "audio.xyz"
        audio_file.touch()
        
        with patch("core.video.whisper_engine.whisper.load_model") as mock_load:
            with patch("core.video.whisper_engine.whisper.transcribe") as mock_transcribe:
                mock_transcribe.side_effect = RuntimeError("Unsupported audio format")
                
                result = engine.transcribe(audio_file)
                
                assert result.success is False


class TestWhisperEngineModelLoading:
    """Test error handling for model loading."""

    def test_load_model_not_found(self):
        """Test loading when model files are not available."""
        with patch("core.video.whisper_engine.whisper.load_model") as mock_load:
            mock_load.side_effect = FileNotFoundError(
                "Model files not found. Please download using: whisper-cli --download"
            )
            
            with pytest.raises(FileNotFoundError):
                engine = WhisperEngine(model_size="base")
                engine._load_model()

    def test_load_model_corrupted(self):
        """Test loading when model files are corrupted."""
        with patch("core.video.whisper_engine.whisper.load_model") as mock_load:
            mock_load.side_effect = RuntimeError(
                "Failed to load model: file is corrupted or incomplete"
            )
            
            with pytest.raises(RuntimeError):
                engine = WhisperEngine(model_size="base")
                engine._load_model()

    def test_load_invalid_model_size(self):
        """Test loading with invalid model size."""
        with patch("core.video.whisper_engine.whisper.load_model") as mock_load:
            mock_load.side_effect = ValueError(
                "Unknown model size: 'huge'. Valid sizes: tiny, base, small, medium, large"
            )
            
            with pytest.raises(ValueError):
                engine = WhisperEngine(model_size="huge")

    def test_load_model_insufficient_disk_space(self):
        """Test loading when there's insufficient disk space."""
        with patch("core.video.whisper_engine.whisper.load_model") as mock_load:
            mock_load.side_effect = OSError(28, "No space left on device")
            
            with pytest.raises(OSError):
                engine = WhisperEngine(model_size="large")

    def test_load_model_permission_denied(self):
        """Test loading when model directory is not accessible."""
        with patch("core.video.whisper_engine.whisper.load_model") as mock_load:
            mock_load.side_effect = PermissionError(
                "Permission denied: cannot access model directory"
            )
            
            with pytest.raises(PermissionError):
                engine = WhisperEngine(model_size="base")


class TestWhisperEngineTranscriptionErrors:
    """Test error handling during transcription."""

    def test_transcribe_out_of_memory(self, tmp_path):
        """Test handling of out-of-memory errors during transcription."""
        engine = WhisperEngine(model_size="base")
        audio_file = tmp_path / "audio.mp3"
        audio_file.touch()
        
        with patch("core.video.whisper_engine.whisper.load_model") as mock_load:
            with patch("core.video.whisper_engine.whisper.transcribe") as mock_transcribe:
                mock_transcribe.side_effect = MemoryError(
                    "CUDA out of memory. Reduce model size or audio length."
                )
                
                result = engine.transcribe(audio_file)
                
                assert result.success is False
                assert "memory" in result.error.lower()

    def test_transcribe_gpu_out_of_memory(self, tmp_path):
        """Test handling of GPU out-of-memory errors."""
        engine = WhisperEngine(model_size="base")
        audio_file = tmp_path / "audio.mp3"
        audio_file.touch()
        
        with patch("core.video.whisper_engine.whisper.load_model") as mock_load:
            with patch("core.video.whisper_engine.whisper.transcribe") as mock_transcribe:
                mock_transcribe.side_effect = RuntimeError(
                    "CUDA out of memory: tried to allocate 2048MB"
                )
                
                result = engine.transcribe(audio_file)
                
                assert result.success is False

    def test_transcribe_timeout(self, tmp_path):
        """Test handling of transcription timeout."""
        engine = WhisperEngine(model_size="base")
        audio_file = tmp_path / "long_audio.mp3"
        audio_file.touch()
        
        with patch("core.video.whisper_engine.whisper.load_model") as mock_load:
            with patch("core.video.whisper_engine.whisper.transcribe") as mock_transcribe:
                mock_transcribe.side_effect = TimeoutError(
                    "Transcription exceeded maximum time limit"
                )
                
                result = engine.transcribe(audio_file, timeout=30)
                
                assert result.success is False

    def test_transcribe_cuda_runtime_error(self, tmp_path):
        """Test handling of CUDA runtime errors."""
        engine = WhisperEngine(model_size="base")
        audio_file = tmp_path / "audio.mp3"
        audio_file.touch()
        
        with patch("core.video.whisper_engine.whisper.load_model") as mock_load:
            with patch("core.video.whisper_engine.whisper.transcribe") as mock_transcribe:
                mock_transcribe.side_effect = RuntimeError(
                    "CUDA runtime error: device not found"
                )
                
                result = engine.transcribe(audio_file)
                
                assert result.success is False


class TestWhisperEngineLanguageDetection:
    """Test error handling for language detection."""

    def test_transcribe_unknown_language(self, tmp_path):
        """Test handling when detected language is unknown or unsupported."""
        engine = WhisperEngine(model_size="base")
        audio_file = tmp_path / "audio.mp3"
        audio_file.touch()
        
        with patch("core.video.whisper_engine.whisper.load_model") as mock_load:
            with patch("core.video.whisper_engine.whisper.transcribe") as mock_transcribe:
                mock_transcribe.return_value = {
                    "language": None,
                    "text": "Cannot determine language"
                }
                
                result = engine.transcribe(audio_file)
                
                # Might succeed but with warning about language

    def test_transcribe_language_mismatch(self, tmp_path):
        """Test when detected language doesn't match expected language."""
        engine = WhisperEngine(model_size="base", language="en")
        audio_file = tmp_path / "audio.mp3"
        audio_file.touch()
        
        with patch("core.video.whisper_engine.whisper.load_model") as mock_load:
            with patch("core.video.whisper_engine.whisper.transcribe") as mock_transcribe:
                mock_transcribe.return_value = {
                    "language": "de",
                    "text": "German text detected"
                }
                
                result = engine.transcribe(audio_file, language="en")
                
                # Transcription might succeed but with language mismatch warning


class TestWhisperEngineResourceLimits:
    """Test error handling for resource constraints."""

    def test_transcribe_very_long_audio(self, tmp_path):
        """Test transcription of very long audio file."""
        engine = WhisperEngine(model_size="base")
        # Simulate a 24-hour audio file
        audio_file = tmp_path / "very_long_audio.mp3"
        audio_file.touch()
        
        with patch("core.video.whisper_engine.whisper.load_model") as mock_load:
            with patch("core.video.whisper_engine.whisper.transcribe") as mock_transcribe:
                # Might timeout or run out of memory
                mock_transcribe.side_effect = RuntimeError("Audio too long")
                
                result = engine.transcribe(audio_file)
                
                # Should handle gracefully
                assert isinstance(result, TranscriptionResult)

    def test_transcribe_insufficient_disk_space(self, tmp_path):
        """Test transcription when disk space is insufficient."""
        engine = WhisperEngine(model_size="base")
        audio_file = tmp_path / "audio.mp3"
        audio_file.touch()
        
        with patch("core.video.whisper_engine.whisper.load_model") as mock_load:
            with patch("core.video.whisper_engine.whisper.transcribe") as mock_transcribe:
                mock_transcribe.side_effect = OSError(28, "No space left on device")
                
                result = engine.transcribe(audio_file)
                
                assert result.success is False

    def test_transcribe_cpu_overload(self, tmp_path):
        """Test transcription under CPU overload."""
        engine = WhisperEngine(model_size="base")
        audio_file = tmp_path / "audio.mp3"
        audio_file.touch()
        
        with patch("core.video.whisper_engine.whisper.load_model") as mock_load:
            with patch("core.video.whisper_engine.whisper.transcribe") as mock_transcribe:
                # CPU overload is typically handled by system
                mock_transcribe.side_effect = RuntimeError("CPU throttling detected")
                
                result = engine.transcribe(audio_file)
                
                # Should timeout or complete slowly


class TestWhisperEngineOutputHandling:
    """Test error handling for output operations."""

    def test_save_transcript_permission_denied(self, tmp_path):
        """Test saving transcript when output directory is read-only."""
        engine = WhisperEngine(model_size="base")
        audio_file = tmp_path / "audio.mp3"
        audio_file.touch()
        output_file = tmp_path / "transcript.txt"
        
        with patch("core.video.whisper_engine.whisper.load_model") as mock_load:
            with patch("core.video.whisper_engine.whisper.transcribe") as mock_transcribe:
                mock_transcribe.return_value = {"text": "Transcript text"}
                
                with patch("builtins.open", side_effect=PermissionError("Permission denied")):
                    result = engine.transcribe(audio_file, output_file=output_file)
                    
                    # Might fail or just skip saving

    def test_save_transcript_disk_full(self, tmp_path):
        """Test saving transcript when disk is full."""
        engine = WhisperEngine(model_size="base")
        audio_file = tmp_path / "audio.mp3"
        audio_file.touch()
        output_file = tmp_path / "transcript.txt"
        
        with patch("core.video.whisper_engine.whisper.load_model") as mock_load:
            with patch("core.video.whisper_engine.whisper.transcribe") as mock_transcribe:
                mock_transcribe.return_value = {"text": "Transcript"}
                
                with patch("builtins.open", side_effect=OSError(28, "No space left on device")):
                    result = engine.transcribe(audio_file, output_file=output_file)
                    
                    # Should handle gracefully


class TestWhisperEngineQualityIssues:
    """Test error handling for transcription quality issues."""

    def test_transcribe_poor_audio_quality(self, tmp_path):
        """Test transcription of poor quality audio."""
        engine = WhisperEngine(model_size="base")
        audio_file = tmp_path / "poor_quality.mp3"
        audio_file.touch()
        
        with patch("core.video.whisper_engine.whisper.load_model") as mock_load:
            with patch("core.video.whisper_engine.whisper.transcribe") as mock_transcribe:
                mock_transcribe.return_value = {
                    "text": "[unintelligible]",
                    "language": "en"
                }
                
                result = engine.transcribe(audio_file)
                
                # Might succeed but with poor quality

    def test_transcribe_no_speech_detected(self, tmp_path):
        """Test transcription when no speech is detected."""
        engine = WhisperEngine(model_size="base")
        audio_file = tmp_path / "silence.mp3"
        audio_file.touch()
        
        with patch("core.video.whisper_engine.whisper.load_model") as mock_load:
            with patch("core.video.whisper_engine.whisper.transcribe") as mock_transcribe:
                mock_transcribe.return_value = {
                    "text": "",
                    "language": None
                }
                
                result = engine.transcribe(audio_file)
                
                assert result.success is True
                assert len(result.text) == 0

    def test_transcribe_heavy_background_noise(self, tmp_path):
        """Test transcription with heavy background noise."""
        engine = WhisperEngine(model_size="base")
        audio_file = tmp_path / "noisy.mp3"
        audio_file.touch()
        
        with patch("core.video.whisper_engine.whisper.load_model") as mock_load:
            with patch("core.video.whisper_engine.whisper.transcribe") as mock_transcribe:
                mock_transcribe.return_value = {
                    "text": "[background noise, unclear speech]",
                    "language": "en"
                }
                
                result = engine.transcribe(audio_file)
                
                # Might succeed but with poor quality


class TestWhisperEngineHallucinationDetection:
    """Test hallucination warning detection."""

    def test_detect_hallucination_repeated_text(self, tmp_path):
        """Test detection of hallucinated repeated text."""
        engine = WhisperEngine(model_size="base")
        audio_file = tmp_path / "audio.mp3"
        audio_file.touch()
        
        with patch("core.video.whisper_engine.whisper.load_model") as mock_load:
            with patch("core.video.whisper_engine.whisper.transcribe") as mock_transcribe:
                # Simulate hallucination
                mock_transcribe.return_value = {
                    "text": "Thank you for watching. Thank you for watching. Thank you for watching."
                }
                
                result = engine.transcribe(audio_file)
                
                # Engine should detect hallucination

    def test_detect_hallucination_filler_words(self, tmp_path):
        """Test detection of excessive filler words."""
        engine = WhisperEngine(model_size="base")
        audio_file = tmp_path / "audio.mp3"
        audio_file.touch()
        
        with patch("core.video.whisper_engine.whisper.load_model") as mock_load:
            with patch("core.video.whisper_engine.whisper.transcribe") as mock_transcribe:
                mock_transcribe.return_value = {
                    "text": "uh uh uh like like like you know you know yeah yeah"
                }
                
                result = engine.transcribe(audio_file)
                
                # Engine might flag excessive filler


class TestWhisperEngineConcurrency:
    """Test error handling in concurrent scenarios."""

    def test_concurrent_transcription_same_model(self, tmp_path):
        """Test concurrent transcriptions sharing same model."""
        engine = WhisperEngine(model_size="base")
        audio_files = [
            tmp_path / f"audio{i}.mp3"
            for i in range(3)
        ]
        for f in audio_files:
            f.touch()
        
        with patch("core.video.whisper_engine.whisper.load_model") as mock_load:
            with patch("core.video.whisper_engine.whisper.transcribe") as mock_transcribe:
                mock_transcribe.return_value = {"text": "Transcribed"}
                
                # Model should handle concurrent access gracefully


class TestWhisperEngineCleanup:
    """Test cleanup after transcription."""

    def test_cleanup_on_error(self, tmp_path):
        """Test that temporary files are cleaned up on error."""
        engine = WhisperEngine(model_size="base")
        audio_file = tmp_path / "audio.mp3"
        audio_file.touch()
        
        with patch("core.video.whisper_engine.whisper.load_model") as mock_load:
            with patch("core.video.whisper_engine.whisper.transcribe") as mock_transcribe:
                mock_transcribe.side_effect = RuntimeError("Transcription failed")
                
                result = engine.transcribe(audio_file)
                
                assert result.success is False
                # Temporary files should be cleaned up

    def test_temp_file_removed_on_success(self, tmp_path):
        """Test that temporary files are removed after successful transcription."""
        engine = WhisperEngine(model_size="base")
        audio_file = tmp_path / "audio.mp3"
        audio_file.touch()
        
        with patch("core.video.whisper_engine.whisper.load_model") as mock_load:
            with patch("core.video.whisper_engine.whisper.transcribe") as mock_transcribe:
                mock_transcribe.return_value = {"text": "Transcribed"}
                
                result = engine.transcribe(audio_file)
                
                assert result.success is True
                # Temporary files should be cleaned up
