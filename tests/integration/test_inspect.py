"""
tests/integration/test_inspect.py

Integration tests for media library inspection functionality using real file operations.

Tests validate the complete media inspection workflow including:
- Media library scanning and metadata extraction
- CSV export functionality
- Error handling for corrupted files
- Recursive directory scanning
- Progress reporting and statistics
"""

import pytest
import csv
from pathlib import Path
from core.video import (
    VIDEO_EXTENSIONS,
    export_to_csv,
    inspect_file,
    scan_directory,
)
from .conftest import create_test_video


class TestInspectScanIntegration:
    """Integration tests for media library scanning functionality."""

    def test_scan_media_directory(self, tmp_path):
        """Test scanning a directory with various media files."""
        # Create test media files with different formats
        formats = ["mp4", "mkv", "avi"]

        created_files = []
        for fmt in formats:
            video_file = create_test_video(
                tmp_path / f"test_video.{fmt}",
                resolution="1920x1080",
                duration=30
            )
            created_files.append(video_file)

        # Scan directory
        videos = scan_directory(tmp_path, recursive=True)

        # Verify results
        assert len(videos) >= len(formats)
        assert all(Path(video.file_path).exists() for video in videos)

        # Verify all formats are detected
        found_extensions = {Path(video.file_path).suffix.lower() for video in videos}
        expected_extensions = {f".{fmt}" for fmt in formats}
        assert expected_extensions.issubset(found_extensions)

    def test_scan_empty_directory(self, tmp_path):
        """Test scanning a directory with no media files."""
        videos = scan_directory(tmp_path, recursive=True)

        # Should find no files
        assert len(videos) == 0

    def test_scan_recursive_directory(self, tmp_path):
        """Test recursive scanning of nested directory structures."""
        # Create nested directory structure
        movies_dir = tmp_path / "Movies"
        movies_dir.mkdir()

        tv_dir = tmp_path / "TV Shows" / "Series Name" / "Season 01"
        tv_dir.mkdir(parents=True)

        docs_dir = tmp_path / "Documents"
        docs_dir.mkdir()

        # Create media files in different locations
        movie = create_test_video(movies_dir / "movie.mp4", resolution="1920x1080", duration=90)
        episode1 = create_test_video(tv_dir / "episode01.mp4", resolution="1280x720", duration=25)
        episode2 = create_test_video(tv_dir / "episode02.mp4", resolution="1280x720", duration=25)

        # Create non-media file in docs
        doc_file = docs_dir / "readme.txt"
        doc_file.write_text("This is not a video file")

        # Scan recursively
        videos = scan_directory(tmp_path, recursive=True)

        # Should find only the video files, not the text file
        assert len(videos) >= 3
        assert all(Path(video.file_path).suffix.lower() in VIDEO_EXTENSIONS for video in videos)

    def test_scan_non_recursive_directory(self, tmp_path):
        """Test non-recursive scanning (only top-level directory)."""
        # Create subdirectory
        sub_dir = tmp_path / "subdir"
        sub_dir.mkdir()

        # Create files in root and subdirectory
        root_video = create_test_video(tmp_path / "root.mp4", resolution="1920x1080", duration=30)
        sub_video = create_test_video(sub_dir / "sub.mp4", resolution="1280x720", duration=25)

        # Scan non-recursively
        videos = scan_directory(tmp_path, recursive=False)

        # Should find only the root video
        assert len(videos) >= 1
        assert any(Path(video.file_path) == root_video for video in videos)
        assert not any(Path(video.file_path) == sub_video for video in videos)


class TestInspectFileAnalysisIntegration:
    """Integration tests for individual file analysis functionality."""

    def test_inspect_single_video_file(self, tmp_path):
        """Test inspecting a single video file."""
        video_file = create_test_video(
            tmp_path / "single_test.mp4",
            resolution="1920x1080",
            duration=60
        )

        # Inspect file
        video_info = inspect_file(video_file)

        # Verify inspection results
        assert Path(video_info.file_path) == video_file
        assert video_info.file_name == "single_test.mp4"
        assert not video_info.probe_error  # Should succeed

        # Verify basic metadata is extracted
        assert video_info.size_gb >= 0
        # Note: Detailed metadata depends on ffprobe output

    def test_inspect_corrupted_video_file(self, tmp_path):
        """Test inspecting a corrupted or invalid video file."""
        # Create a file with video extension but invalid content
        corrupted_file = tmp_path / "corrupted.mp4"
        corrupted_file.write_bytes(b"This is not a valid video file")

        # Inspect file
        video_info = inspect_file(corrupted_file)

        # Should handle error gracefully
        assert Path(video_info.file_path) == corrupted_file
        assert video_info.probe_error

    def test_inspect_nonexistent_file(self, tmp_path):
        """Test inspecting a file that doesn't exist."""
        nonexistent = tmp_path / "does_not_exist.mp4"

        # This should raise an exception or return error
        with pytest.raises((FileNotFoundError, OSError)):
            inspect_file(nonexistent)


class TestInspectCSVExportIntegration:
    """Integration tests for CSV export functionality."""

    def test_export_to_csv_basic(self, tmp_path):
        """Test basic CSV export functionality."""
        # Create test video files
        videos = []
        for i in range(3):
            video_file = create_test_video(
                tmp_path / f"export_test_{i}.mp4",
                resolution="1280x720",
                duration=30
            )
            video_info = inspect_file(video_file)
            videos.append(video_info)

        # Export to CSV
        csv_file = tmp_path / "test_export.csv"
        export_to_csv(videos, csv_file, delimiter=";")

        # Verify CSV file was created
        assert csv_file.exists()
        assert csv_file.stat().st_size > 0

        # Verify CSV content
        with open(csv_file, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f, delimiter=';')
            rows = list(reader)

        assert len(rows) == len(videos)

        # Verify headers exist
        fieldnames = reader.fieldnames
        assert fieldnames is not None
        assert "Dateiname" in fieldnames
        assert "Pfad" in fieldnames

    def test_export_to_csv_with_errors(self, tmp_path):
        """Test CSV export when some files have errors."""
        # Create valid video
        valid_video = create_test_video(
            tmp_path / "valid.mp4",
            resolution="1920x1080",
            duration=30
        )
        valid_info = inspect_file(valid_video)

        # Create "corrupted" video
        corrupted_file = tmp_path / "corrupted.mp4"
        corrupted_file.write_bytes(b"invalid")
        corrupted_info = inspect_file(corrupted_file)

        videos = [valid_info, corrupted_info]

        # Export to CSV
        csv_file = tmp_path / "error_export.csv"
        export_to_csv(videos, csv_file, delimiter=";")

        # Verify CSV was created despite errors
        assert csv_file.exists()

        with open(csv_file, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f, delimiter=';')
            rows = list(reader)

        assert len(rows) == 2  # Both entries should be in CSV

    def test_export_to_csv_different_delimiters(self, tmp_path):
        """Test CSV export with different delimiters."""
        video_file = create_test_video(
            tmp_path / "delimiter_test.mp4",
            resolution="1280x720",
            duration=30
        )
        video_info = inspect_file(video_file)

        # Test with comma delimiter
        csv_comma = tmp_path / "comma.csv"
        export_to_csv([video_info], csv_comma, delimiter=",")

        with open(csv_comma, 'r', encoding='utf-8-sig') as f:
            content = f.read()
            assert "," in content

        # Test with semicolon delimiter
        csv_semicolon = tmp_path / "semicolon.csv"
        export_to_csv([video_info], csv_semicolon, delimiter=";")

        with open(csv_semicolon, 'r', encoding='utf-8-sig') as f:
            content = f.read()
            assert ";" in content


class TestInspectWorkflowIntegration:
    """Integration tests for complete inspection workflow."""

    def test_complete_inspection_workflow(self, tmp_path):
        """Test the complete media inspection workflow."""
        # Step 1: Create a media library structure
        library_dir = tmp_path / "MediaLibrary"
        library_dir.mkdir()

        movies_dir = library_dir / "Movies"
        movies_dir.mkdir()

        tv_dir = library_dir / "TV Shows" / "Example Show" / "Season 1"
        tv_dir.mkdir(parents=True)

        # Create various media files
        media_files = [
            movies_dir / "Action_Movie.mp4",
            movies_dir / "Comedy_Movie.mkv",
            tv_dir / "Episode_01.mp4",
            tv_dir / "Episode_02.mp4",
            tv_dir / "Episode_03.mp4",
        ]

        for media_file in media_files:
            create_test_video(
                media_file,
                resolution="1920x1080" if "Movie" in str(media_file) else "1280x720",
                duration=45 if "Movie" in str(media_file) else 25
            )

        # Step 2: Scan the library
        videos = scan_directory(library_dir, recursive=True)

        # Verify all files were found
        assert len(videos) >= len(media_files)

        # Step 3: Export to CSV
        csv_output = library_dir / "library_inventory.csv"
        export_to_csv(videos, csv_output, delimiter=";")

        # Verify CSV was created
        assert csv_output.exists()

        # Step 4: Verify CSV content
        with open(csv_output, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f, delimiter=';')
            csv_rows = list(reader)

        assert len(csv_rows) == len(videos)

        # Step 5: Verify statistics
        movies_count = sum(1 for video in videos if "Movie" in video.file_name)
        tv_count = sum(1 for video in videos if "Episode" in video.file_name)

        assert movies_count >= 2
        assert tv_count >= 3

        # Step 6: Verify no errors in successful scans
        successful_scans = [v for v in videos if not v.probe_error]
        assert len(successful_scans) == len(videos)  # All should succeed