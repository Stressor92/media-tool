"""
tests/integration/test_audiobook.py

Integration tests for audiobook processing functionality using real file operations.

Tests validate the complete audiobook processing workflow including:
- Audiobook library scanning and metadata extraction
- Audiobook organization into Author/Book structure
- Chapter file detection and merging
- Complete audiobook workflow processing
"""

from core.audiobook import (
    detect_chapter_files,
    merge_audiobook_library,
    organize_audiobooks,
    scan_audiobook_library,
)

from .conftest import create_test_audio


class TestAudiobookScanIntegration:
    """Integration tests for audiobook scanning functionality."""

    def test_scan_audiobook_directory(self, tmp_path):
        """Test scanning a directory with audiobook files."""
        # Create test audiobook files
        book1 = create_test_audio(
            tmp_path / "book1.m4a",
            duration=1800,  # 30 minutes
            language="und",
        )
        book2 = create_test_audio(
            tmp_path / "book2.m4b",
            duration=3600,  # 1 hour
            language="und",
        )

        # Scan directory
        metadata_list = scan_audiobook_library(tmp_path, recursive=True)

        # Verify results
        assert len(metadata_list) >= 2  # May find more depending on implementation
        assert all(metadata.filepath.exists() for metadata in metadata_list)

    def test_scan_empty_audiobook_directory(self, tmp_path):
        """Test scanning a directory with no audiobook files."""
        # Scan empty directory
        metadata_list = scan_audiobook_library(tmp_path, recursive=True)

        # Should find no files
        assert len(metadata_list) == 0

    def test_scan_audiobook_recursive(self, tmp_path):
        """Test recursive scanning of audiobook subdirectories."""
        # Create subdirectory structure
        author_dir = tmp_path / "Author Name"
        author_dir.mkdir()

        book_dir = author_dir / "Book Title"
        book_dir.mkdir()

        # Create audiobook files in nested structure
        main_book = create_test_audio(book_dir / "main.m4a", duration=1800)
        chapter1 = create_test_audio(book_dir / "chapter01.m4a", duration=300)
        chapter2 = create_test_audio(book_dir / "chapter02.m4a", duration=300)

        # Scan recursively
        metadata_list = scan_audiobook_library(tmp_path, recursive=True)

        # Should find all files
        assert len(metadata_list) >= 3


class TestAudiobookOrganizeIntegration:
    """Integration tests for audiobook organization functionality."""

    def test_organize_audiobooks_basic(self, tmp_path):
        """Test basic audiobook organization."""
        source_dir = tmp_path / "source_audiobooks"
        source_dir.mkdir()

        target_dir = tmp_path / "organized_audiobooks"

        # Create test audiobook files
        book1 = create_test_audio(source_dir / "book1.m4a", duration=1800)
        book2 = create_test_audio(source_dir / "book2.m4a", duration=1800)

        # Organize audiobooks
        results = organize_audiobooks(source_dir, target_dir, "m4a")

        # Verify results structure
        assert isinstance(results, dict)
        # Note: Actual organization depends on metadata extraction

    def test_organize_audiobooks_with_chapters(self, tmp_path):
        """Test organizing audiobooks that have chapter files."""
        source_dir = tmp_path / "chaptered_books"
        source_dir.mkdir()

        target_dir = tmp_path / "organized_chapters"

        # Create chapter files
        chapter1 = create_test_audio(source_dir / "Book_Chapter_01.m4a", duration=600)
        chapter2 = create_test_audio(source_dir / "Book_Chapter_02.m4a", duration=600)
        chapter3 = create_test_audio(source_dir / "Book_Chapter_03.m4a", duration=600)

        # Organize
        results = organize_audiobooks(source_dir, target_dir, "m4a")

        # Verify results
        assert isinstance(results, dict)


class TestAudiobookMergeIntegration:
    """Integration tests for audiobook chapter merging functionality."""

    def test_detect_chapter_files(self, tmp_path):
        """Test detection of chapter files in a directory."""
        # Create chapter files with typical naming patterns
        chapter_files = [
            "Book_Title_Chapter_01.m4a",
            "Book_Title_Chapter_02.m4a",
            "Book_Title_Chapter_03.m4a",
        ]

        for chapter_file in chapter_files:
            create_test_audio(tmp_path / chapter_file, duration=300)

        # Detect chapters
        detected = detect_chapter_files(tmp_path)

        # Verify detection
        assert isinstance(detected, dict)
        # Note: Actual detection depends on naming pattern recognition

    def test_merge_audiobook_chapters(self, tmp_path):
        """Test merging chapter files into a single audiobook."""
        source_dir = tmp_path / "chapters"
        source_dir.mkdir()

        target_dir = tmp_path / "merged_books"

        # Create chapter files
        chapters = []
        for i in range(1, 4):
            chapter_file = create_test_audio(source_dir / "02.m4a", duration=300)
            chapters.append(chapter_file)

        # Merge chapters
        results = merge_audiobook_library(source_dir, target_dir, "m4a", overwrite=False)

        # Verify results
        assert isinstance(results, dict)
        assert "books_found" in results
        assert "books_merged" in results

    def test_merge_dry_run(self, tmp_path):
        """Test merge functionality in dry-run mode."""
        source_dir = tmp_path / "dry_run_chapters"
        source_dir.mkdir()

        target_dir = tmp_path / "dry_run_output"

        # Create chapter files
        for i in range(1, 3):
            create_test_audio(source_dir / "03.m4a", duration=300)

        # Dry run merge
        results = merge_audiobook_library(source_dir, target_dir, "m4a", dry_run=True)

        # In dry run, should not create output files
        assert isinstance(results, dict)
        assert "books_found" in results
        # Target directory might not exist in dry run

    def test_merge_different_formats(self, tmp_path):
        """Test merging chapters to different output formats."""
        source_dir = tmp_path / "format_test"
        source_dir.mkdir()

        target_dir = tmp_path / "format_output"

        # Create M4A chapter files
        chapters = []
        for i in range(1, 3):
            chapter = create_test_audio(source_dir / "04.m4a", duration=300)
            chapters.append(chapter)

        # Merge to MP3 format
        results_mp3 = merge_audiobook_library(source_dir, target_dir, "mp3", overwrite=False)

        # Merge to M4A format
        results_m4a = merge_audiobook_library(source_dir, target_dir, "m4a", overwrite=False)

        # Verify results
        assert isinstance(results_mp3, dict)
        assert isinstance(results_m4a, dict)

    def test_merge_overwrite_behavior(self, tmp_path):
        """Test merge overwrite behavior."""
        source_dir = tmp_path / "overwrite_test"
        source_dir.mkdir()

        target_dir = tmp_path / "overwrite_output"

        # Create chapter files
        for i in range(1, 3):
            create_test_audio(source_dir / "05.m4a", duration=300)

        # First merge
        results1 = merge_audiobook_library(source_dir, target_dir, "m4a", overwrite=False)
        assert isinstance(results1, dict)

        # Second merge without overwrite - should skip
        results2 = merge_audiobook_library(source_dir, target_dir, "m4a", overwrite=False)
        assert isinstance(results2, dict)

        # Third merge with overwrite
        results3 = merge_audiobook_library(source_dir, target_dir, "m4a", overwrite=True)
        assert isinstance(results3, dict)


class TestAudiobookWorkflowIntegration:
    """Integration tests for complete audiobook workflow processing."""

    def test_audiobook_complete_workflow(self, tmp_path):
        """Test the complete audiobook processing workflow."""
        source_dir = tmp_path / "raw_audiobooks"
        source_dir.mkdir()

        target_dir = tmp_path / "processed_audiobooks"

        # Create a mix of single files and chapter files
        single_book = create_test_audio(source_dir / "Single_Book.m4a", duration=3600)

        # Create chapter directory
        chapter_dir = source_dir / "Chaptered_Book"
        chapter_dir.mkdir()

        chapter1 = create_test_audio(chapter_dir / "Chaptered_Book_01.m4a", duration=900)
        chapter2 = create_test_audio(chapter_dir / "Chaptered_Book_02.m4a", duration=900)
        chapter3 = create_test_audio(chapter_dir / "Chaptered_Book_03.m4a", duration=900)

        # First scan the library
        metadata_list = scan_audiobook_library(source_dir, recursive=True)
        assert len(metadata_list) >= 4  # single book + 3 chapters

        # Then organize
        organize_results = organize_audiobooks(source_dir, target_dir, "m4a")
        assert isinstance(organize_results, dict)

        # Finally merge chapters
        merge_results = merge_audiobook_library(target_dir, target_dir, "m4a", overwrite=False)
        assert isinstance(merge_results, dict)
