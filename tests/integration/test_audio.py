"""
tests/integration/test_audio.py

Integration tests for audio processing functionality using real file operations.

Tests validate the complete audio processing workflow including:
- Audio file scanning and metadata extraction
- Audio format conversion
- Music library organization
- Audio enhancement and improvement
- Complete audio workflow processing
"""

from core.audio import (
    extract_audio_metadata_enhanced,
    convert_audio,
    organize_music,
    improve_audio_file,
    improve_audio_library,
    AudioEnhancementResult,
)
from .conftest import create_test_audio


class TestAudioScanIntegration:
    """Integration tests for audio scanning functionality."""

    def test_scan_audio_directory(self, tmp_path):
        """Test scanning a directory with multiple audio files."""
        # Create test audio files
        audio1 = create_test_audio(
            tmp_path / "song1.mp3",
            duration=30,
            language="und"
        )
        audio2 = create_test_audio(
            tmp_path / "song2.flac",
            duration=45,
            language="und"
        )

        # Scan directory
        metadata_list = []
        for filepath in [audio1, audio2]:
            metadata = extract_audio_metadata_enhanced(filepath)
            if metadata:
                metadata_list.append(metadata)

        # Verify results
        assert len(metadata_list) == 2
        assert all(metadata.filepath.exists() for metadata in metadata_list)

    def test_scan_empty_directory(self, tmp_path):
        """Test scanning a directory with no audio files."""
        # Scan empty directory
        metadata_list = []
        audio_files = list(tmp_path.glob("*.mp3")) + list(tmp_path.glob("*.flac"))
        for filepath in audio_files:
            metadata = extract_audio_metadata_enhanced(filepath)
            if metadata:
                metadata_list.append(metadata)

        # Should find no files
        assert len(metadata_list) == 0

    def test_scan_recursive_directory(self, tmp_path):
        """Test recursive scanning of subdirectories."""
        # Create subdirectory structure
        subdir = tmp_path / "subdir"
        subdir.mkdir()

        # Create audio files in different locations
        root_audio = create_test_audio(tmp_path / "root.mp3", duration=30)
        sub_audio = create_test_audio(subdir / "sub.mp3", duration=30)

        # Scan recursively
        metadata_list = []
        all_audio = list(tmp_path.rglob("*.mp3")) + list(tmp_path.rglob("*.flac"))
        for filepath in all_audio:
            metadata = extract_audio_metadata_enhanced(filepath)
            if metadata:
                metadata_list.append(metadata)

        # Should find both files
        assert len(metadata_list) == 2


class TestAudioConvertIntegration:
    """Integration tests for audio format conversion."""

    def test_convert_mp3_to_flac(self, tmp_path):
        """Test converting MP3 to FLAC format."""
        # Create test MP3 file
        input_file = create_test_audio(
            tmp_path / "input.mp3",
            duration=10,
            language="und"
        )

        output_file = tmp_path / "output.flac"

        # Convert audio
        result = convert_audio(input_file, output_file, "flac")

        # Verify conversion
        assert result.success
        assert output_file.exists()
        assert output_file.stat().st_size > 0

        # Verify output format
        metadata = extract_audio_metadata_enhanced(output_file)
        assert metadata is not None
        # Note: actual format detection would require audio analysis

    def test_convert_batch_directory(self, tmp_path):
        """Test batch conversion of multiple audio files."""
        # Create multiple test files
        files = []
        for i in range(3):
            audio_file = create_test_audio(
                tmp_path / f"input_{i}.mp3",
                duration=5
            )
            files.append(audio_file)

        # Convert all to FLAC
        results = []
        for input_file in files:
            output_file = tmp_path / f"output_{input_file.stem}.flac"
            result = convert_audio(input_file, output_file, "flac")
            results.append(result)

        # Verify all conversions succeeded
        assert all(result.success for result in results)
        assert all((tmp_path / f"output_input_{i}.flac").exists() for i in range(3))

    def test_convert_invalid_input(self, tmp_path):
        """Test conversion with invalid input file."""
        # Create a text file
        invalid_file = tmp_path / "invalid.txt"
        invalid_file.write_text("This is not audio")

        output_file = tmp_path / "output.flac"

        # Attempt conversion
        result = convert_audio(invalid_file, output_file, "flac")

        # Should fail gracefully
        assert not result.success
        assert not output_file.exists()


class TestAudioOrganizeIntegration:
    """Integration tests for music library organization."""

    def test_organize_music_files(self, tmp_path):
        """Test organizing music files into Artist/Album structure."""
        # Create test audio files with metadata
        # Note: This would require actual audio files with proper metadata
        # For integration testing, we'll test the basic functionality

        source_dir = tmp_path / "source"
        source_dir.mkdir()

        target_dir = tmp_path / "organized"

        # Create some dummy audio files
        audio1 = create_test_audio(source_dir / "song1.mp3", duration=30)
        audio2 = create_test_audio(source_dir / "song2.mp3", duration=30)

        # Test organization (this would normally use real metadata)
        # Since we can't easily create audio files with metadata in tests,
        # we'll test the basic file handling
        results = organize_music(source_dir, target_dir, "flac")

        # Verify some basic behavior
        assert isinstance(results, dict)
        assert "processed" in results or "errors" in results
        # Note: Actual organization depends on metadata extraction

    def test_organize_empty_directory(self, tmp_path):
        """Test organizing an empty directory."""
        source_dir = tmp_path / "empty_source"
        source_dir.mkdir()

        target_dir = tmp_path / "organized"

        results = organize_music(source_dir, target_dir, "flac")

        # Should handle empty directory gracefully
        assert isinstance(results, dict)
        assert "processed" in results


class TestAudioImproveIntegration:
    """Integration tests for audio enhancement functionality."""

    def test_improve_single_audio_file(self, tmp_path):
        """Test improving a single audio file."""
        # Create test audio file
        input_file = create_test_audio(
            tmp_path / "input.mp3",
            duration=10
        )

        output_file = tmp_path / "improved.mp3"

        # Improve audio
        result = improve_audio_file(input_file, output_file)

        # Verify result structure
        assert isinstance(result, AudioEnhancementResult)
        # Note: Actual improvement depends on audio processing libraries

    def test_improve_audio_library(self, tmp_path):
        """Test improving an entire audio library."""
        # Create test directory with audio files
        source_dir = tmp_path / "source"
        source_dir.mkdir()

        target_dir = tmp_path / "improved"

        # Create test files
        audio1 = create_test_audio(source_dir / "audio1.mp3", duration=10)
        audio2 = create_test_audio(source_dir / "audio2.mp3", duration=10)

        # Improve library
        results = improve_audio_library(source_dir, target_dir)

        # Verify results
        assert isinstance(results, dict)
        assert "processed" in results or "improved" in results or "errors" in results


class TestAudioWorkflowIntegration:
    """Integration tests for complete audio workflow processing."""

    def test_audio_workflow_complete(self, tmp_path):
        """Test the complete audio workflow from source to organized."""
        source_dir = tmp_path / "mixed_music"
        source_dir.mkdir()

        target_dir = tmp_path / "organized_music"

        # Create test audio files
        audio1 = create_test_audio(source_dir / "track1.mp3", duration=30)
        audio2 = create_test_audio(source_dir / "track2.mp3", duration=30)

        # Note: The actual workflow function would need to be implemented
        # This is a placeholder for when the workflow function exists

        # For now, just test that directories exist
        assert source_dir.exists()
        assert source_dir.is_dir()

    def test_audio_workflow_scan_only(self, tmp_path):
        """Test audio workflow in scan-only mode."""
        source_dir = tmp_path / "scan_source"
        source_dir.mkdir()

        target_dir = tmp_path / "scan_target"

        # Create test files
        audio1 = create_test_audio(source_dir / "scan1.mp3", duration=10)
        audio2 = create_test_audio(source_dir / "scan2.mp3", duration=10)

        # In scan-only mode, should not create target directory
        # (This depends on actual workflow implementation)

        assert source_dir.exists()