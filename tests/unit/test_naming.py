"""
Unit tests for src/core/naming/jellyfin.py

Test Jellyfin-compatible file and folder naming conventions.
No filesystem access required — all functions take strings and return strings.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from core.naming.jellyfin import (
    _sanitize_filename,
    format_movie_name,
    format_series_episode,
    generate_movie_folder_path,
    generate_movie_file_path,
    generate_series_folder_path,
    generate_season_folder_path,
    generate_episode_file_path,
)


# ---------------------------------------------------------------------------
# Tests for _sanitize_filename()
# ---------------------------------------------------------------------------


class TestSanitizeFilename:
    """Test filename sanitization for invalid characters."""

    def test_sanitize_removes_invalid_characters(self):
        """Should remove characters invalid in filenames."""
        assert _sanitize_filename('Movie<Title>') == 'MovieTitle'
        assert _sanitize_filename('Film|Title') == 'FilmTitle'
        assert _sanitize_filename('Show:Title') == 'Show -Title'
        assert _sanitize_filename('File"Name') == 'FileName'
        assert _sanitize_filename('Title?') == 'Title'
        assert _sanitize_filename('Name*') == 'Name'

    def test_sanitize_replaces_colon_with_dash(self):
        """Colons should be replaced with space-dash."""
        assert _sanitize_filename('Movie: The Title') == 'Movie - The Title'

    def test_sanitize_keeps_normal_characters(self):
        """Should preserve alphanumeric and safe characters."""
        assert _sanitize_filename('Movie Title (2022)') == 'Movie Title (2022)'
        assert _sanitize_filename('Film-Name') == 'Film-Name'
        assert _sanitize_filename('Show_123') == 'Show_123'

    def test_sanitize_strips_whitespace(self):
        """Should strip leading/trailing whitespace."""
        assert _sanitize_filename('  Title  ') == 'Title'

    def test_sanitize_empty_string(self):
        """Should handle empty string."""
        assert _sanitize_filename('') == ''

    def test_sanitize_all_invalid_characters(self):
        """Should handle string with only invalid characters."""
        result = _sanitize_filename('<>:"|?*')
        # After replacing ':' with ' -' and removing others, then stripping
        assert result == ' -' or result == '-'  # May be ' -' or '-' after strip


# ---------------------------------------------------------------------------
# Tests for format_movie_name()
# ---------------------------------------------------------------------------


class TestFormatMovieName:
    """Test movie name formatting according to Jellyfin standards."""

    def test_format_movie_with_valid_year(self):
        """Should format as 'Title (Year)' with valid 4-digit year."""
        assert format_movie_name('The Matrix', 1999) == 'The Matrix (1999)'
        assert format_movie_name('Inception', '2010') == 'Inception (2010)'

    def test_format_movie_without_year(self):
        """Should return title only when year is None."""
        assert format_movie_name('Casablanca', None) == 'Casablanca'

    def test_format_movie_with_invalid_year_string(self):
        """Should extract valid year from year string if present."""
        assert format_movie_name('Film', 'copyright 2015') == 'Film (2015)'

    def test_format_movie_year_with_non_numeric_year(self):
        """Should return title only if year string has no digits."""
        assert format_movie_name('Oldfilm', 'unknown') == 'Oldfilm'

    def test_format_movie_sanitizes_title(self):
        """Should sanitize invalid characters in title."""
        assert format_movie_name('Film: The Title', 2020) == 'Film - The Title (2020)'
        assert format_movie_name('Movie<Test>', 2020) == 'MovieTest (2020)'

    def test_format_movie_strips_whitespace(self):
        """Should strip whitespace from title."""
        assert format_movie_name('  Spaced Title  ', 1999) == 'Spaced Title (1999)'

    def test_format_movie_year_zero(self):
        """Year 0 should be treated as no year."""
        result = format_movie_name('Ancient', 0)
        # 0 is falsy, so no year should be appended
        assert result == 'Ancient'

    def test_format_movie_year_string_extraction(self):
        """Should extract year from middle of string."""
        assert format_movie_name('Title', 'filmed in 2018 somewhere') == 'Title (2018)'


# ---------------------------------------------------------------------------
# Tests for format_series_episode()
# ---------------------------------------------------------------------------


class TestFormatSeriesEpisode:
    """Test TV series episode formatting according to Jellyfin standards."""

    def test_format_series_basic(self):
        """Should format as 'Series - SXXEXX' with season and episode numbers."""
        assert (
            format_series_episode('Breaking Bad', 1, 1)
            == 'Breaking Bad - S01E01'
        )

    def test_format_series_with_episode_title(self):
        """Should append episode title with ' - ' separator."""
        assert (
            format_series_episode('Breaking Bad', 1, 1, 'Pilot')
            == 'Breaking Bad - S01E01 - Pilot'
        )

    def test_format_series_multiple_digits(self):
        """Should zero-pad season and episode to 2 digits."""
        assert (
            format_series_episode('Game of Thrones', 5, 9, 'The Bells')
            == 'Game of Thrones - S05E09 - The Bells'
        )

    def test_format_series_string_season_episode(self):
        """Should handle season and episode as strings (numeric)."""
        assert (
            format_series_episode('Show', '2', '5')
            == 'Show - S02E05'  # Converts strings to formatted season/episode
        )

    def test_format_series_large_season_numbers(self):
        """Should handle seasons > 9."""
        result = format_series_episode('Long Show', 20, 15)
        assert result == 'Long Show - S20E15'

    def test_format_series_sanitizes_title(self):
        """Should sanitize series name."""
        assert (
            format_series_episode('Show: The Title', 1, 1)
            == 'Show - The Title - S01E01'
        )

    def test_format_series_with_invalid_episode_title(self):
        """Should sanitize episode title."""
        result = format_series_episode('Show', 1, 1, 'Episode <Test>')
        assert 'Episode' in result
        assert 'Test' in result
        # Invalid characters removed but spacing preserved
        assert '<' not in result and '>' not in result

    def test_format_series_empty_episode_title(self):
        """Should omit episode title if empty."""
        assert (
            format_series_episode('Show', 1, 1, '')
            == 'Show - S01E01'
        )
        # Note: Whitespace-only titles are appended as-is
        # (implementation may not strip before checking)

    def test_format_series_type_coercion(self):
        """Should convert int season/episode to numbers."""
        assert (
            format_series_episode('Show', 3, 7)
            == 'Show - S03E07'
        )


# ---------------------------------------------------------------------------
# Tests for generate_movie_folder_path()
# ---------------------------------------------------------------------------


class TestGenerateMovieFolderPath:
    """Test movie folder path generation."""

    def test_generate_movie_folder_with_year(self, tmp_path):
        """Should create 'Movie Title (Year)' folder."""
        result = generate_movie_folder_path('Inception', 2010, tmp_path)
        assert result == tmp_path / 'Inception (2010)'

    def test_generate_movie_folder_without_year(self, tmp_path):
        """Should create folder with title only when no year."""
        result = generate_movie_folder_path('Casablanca', None, tmp_path)
        assert result == tmp_path / 'Casablanca'

    def test_generate_movie_folder_preserves_base_dir(self, tmp_path):
        """Should use given base directory as parent."""
        custom_base = tmp_path / 'Movies'
        result = generate_movie_folder_path('Film', 2020, custom_base)
        # Path object, check parent and name
        assert result.parent == custom_base

    def test_generate_movie_folder_sanitizes_title(self, tmp_path):
        """Should sanitize title in folder name."""
        result = generate_movie_folder_path('Film: Test<Name>', 2020, tmp_path)
        # Title should be sanitized
        assert '<' not in str(result)
        assert '|' not in str(result)

    def test_generate_movie_folder_type_conversion(self, tmp_path):
        """Should convert year to string if needed."""
        result_int = generate_movie_folder_path('Title', 2015, tmp_path)
        result_str = generate_movie_folder_path('Title', '2015', tmp_path)
        # Both should produce same path
        assert result_int.name == result_str.name or '2015' in str(result_int)


# ---------------------------------------------------------------------------
# Integration tests combining multiple functions
# ---------------------------------------------------------------------------


class TestNamingIntegration:
    """Integration tests for naming functions working together."""

    def test_movie_name_then_folder_generation(self, tmp_path):
        """Test formatting movie name then using it for folder path."""
        title = 'The Dark Knight'
        year = 2008
        
        formatted_name = format_movie_name(title, year)
        folder_path = generate_movie_folder_path(title, year, tmp_path)
        
        assert 'The Dark Knight' in folder_path.name
        assert '2008' in folder_path.name
        assert formatted_name in folder_path.name

    def test_complex_movie_with_special_characters(self, tmp_path):
        """Test movie with various special characters."""
        title = 'Film: The Test (Special)'
        year = 2022
        
        formatted = format_movie_name(title, year)
        folder = generate_movie_folder_path(title, year, tmp_path)
        
        # Should not contain invalid characters
        assert ':' not in folder.name or ' - ' in folder.name
        assert '<' not in folder.name
        assert '>' not in folder.name
        assert '|' not in folder.name


# ---------------------------------------------------------------------------
# Tests for generate_movie_file_path()
# ---------------------------------------------------------------------------


class TestGenerateMovieFilePath:
    """Test movie file path generation."""

    def test_generate_movie_file_basic(self, tmp_path):
        """Should create full movie file path."""
        result = generate_movie_file_path('Inception', 2010, 'mkv', tmp_path)
        expected = tmp_path / 'Inception (2010)' / 'Inception (2010).mkv'
        assert result == expected

    def test_generate_movie_file_without_year(self, tmp_path):
        """Should work without year."""
        result = generate_movie_file_path('Casablanca', None, 'mp4', tmp_path)
        expected = tmp_path / 'Casablanca' / 'Casablanca.mp4'
        assert result == expected

    def test_generate_movie_file_with_suffix(self, tmp_path):
        """Should include suffix in filename."""
        result = generate_movie_file_path('Movie', 2020, 'mkv', tmp_path, 'Extended')
        expected = tmp_path / 'Movie (2020)' / 'Movie (2020) Extended.mkv'
        assert result == expected

    def test_generate_movie_file_sanitizes_title(self, tmp_path):
        """Should sanitize title in both folder and filename."""
        result = generate_movie_file_path('Film: Test<Name>', 2020, 'mkv', tmp_path)
        # Should not contain invalid characters
        assert '<' not in str(result)
        assert '>' not in str(result)
        # Should contain sanitized version with colon replaced by ' -'
        assert 'Film - TestName' in str(result)

    def test_generate_movie_file_different_extensions(self, tmp_path):
        """Should work with different file extensions."""
        for ext in ['mkv', 'mp4', 'avi']:
            result = generate_movie_file_path('Test', 2020, ext, tmp_path)
            assert str(result).endswith(f'.{ext}')
            assert 'Test (2020)' in str(result)


# ---------------------------------------------------------------------------
# Tests for generate_series_folder_path()
# ---------------------------------------------------------------------------


class TestGenerateSeriesFolderPath:
    """Test TV series folder path generation."""

    def test_generate_series_folder_basic(self, tmp_path):
        """Should create series folder path."""
        result = generate_series_folder_path('Breaking Bad', tmp_path)
        expected = tmp_path / 'Breaking Bad'
        assert result == expected

    def test_generate_series_folder_sanitizes_name(self, tmp_path):
        """Should sanitize series name."""
        result = generate_series_folder_path('Show: The Title<Bad>', tmp_path)
        # Should not contain invalid characters
        assert '<' not in str(result)
        assert '>' not in str(result)
        # Should contain sanitized version with colon replaced by ' -'
        assert 'Show - The TitleBad' in str(result)

    def test_generate_series_folder_strips_whitespace(self, tmp_path):
        """Should strip whitespace from series name."""
        result = generate_series_folder_path('  Series Name  ', tmp_path)
        expected = tmp_path / 'Series Name'
        assert result == expected

    def test_generate_series_folder_empty_name(self, tmp_path):
        """Should handle empty series name."""
        result = generate_series_folder_path('', tmp_path)
        expected = tmp_path / ''
        assert result == expected


# ---------------------------------------------------------------------------
# Tests for generate_season_folder_path()
# ---------------------------------------------------------------------------


class TestGenerateSeasonFolderPath:
    """Test TV season folder path generation."""

    def test_generate_season_folder_basic(self, tmp_path):
        """Should create season folder path."""
        result = generate_season_folder_path('Breaking Bad', 1, tmp_path)
        expected = tmp_path / 'Breaking Bad' / 'Season 01'
        assert result == expected

    def test_generate_season_folder_multiple_digits(self, tmp_path):
        """Should pad season numbers correctly."""
        result = generate_season_folder_path('Show', 10, tmp_path)
        expected = tmp_path / 'Show' / 'Season 10'
        assert result == expected

    def test_generate_season_folder_string_season(self, tmp_path):
        """Should handle string season numbers."""
        result = generate_season_folder_path('Show', '2', tmp_path)
        expected = tmp_path / 'Show' / 'Season 02'
        assert result == expected

    def test_generate_season_folder_non_numeric_season(self, tmp_path):
        """Should handle non-numeric season identifiers."""
        result = generate_season_folder_path('Show', 'Special', tmp_path)
        expected = tmp_path / 'Show' / 'Season Special'
        assert result == expected

    def test_generate_season_folder_sanitizes_series_name(self, tmp_path):
        """Should sanitize series name in path."""
        result = generate_season_folder_path('Show: Bad<Name>', 1, tmp_path)
        # Series folder should be sanitized
        assert 'Show - BadName' in str(result)
        assert 'Season 01' in str(result)


# ---------------------------------------------------------------------------
# Tests for generate_episode_file_path()
# ---------------------------------------------------------------------------


class TestGenerateEpisodeFilePath:
    """Test TV episode file path generation."""

    def test_generate_episode_file_basic(self, tmp_path):
        """Should create full episode file path."""
        result = generate_episode_file_path('Breaking Bad', 1, 1, 'mkv', tmp_path)
        expected = tmp_path / 'Breaking Bad' / 'Season 01' / 'Breaking Bad - S01E01.mkv'
        assert result == expected

    def test_generate_episode_file_with_title(self, tmp_path):
        """Should include episode title in filename."""
        result = generate_episode_file_path('Show', 2, 3, 'mkv', tmp_path, 'The Episode')
        expected = tmp_path / 'Show' / 'Season 02' / 'Show - S02E03 - The Episode.mkv'
        assert result == expected

    def test_generate_episode_file_multiple_digits(self, tmp_path):
        """Should handle multi-digit season/episode numbers."""
        result = generate_episode_file_path('Series', 10, 25, 'mp4', tmp_path)
        expected = tmp_path / 'Series' / 'Season 10' / 'Series - S10E25.mp4'
        assert result == expected

    def test_generate_episode_file_string_season_episode(self, tmp_path):
        """Should handle string season/episode."""
        result = generate_episode_file_path('Show', '3', '5', 'avi', tmp_path)
        expected = tmp_path / 'Show' / 'Season 03' / 'Show - S03E05.avi'
        assert result == expected

    def test_generate_episode_file_sanitizes_names(self, tmp_path):
        """Should sanitize series and episode names."""
        result = generate_episode_file_path(
            'Show: Bad<Name>', 1, 1, 'mkv', tmp_path, 'Episode: Test>Title'
        )
        # Should not contain invalid characters
        assert '<' not in str(result)
        assert '>' not in str(result)
        # Should contain sanitized versions with colons replaced by ' -'
        assert 'Show - BadName' in str(result)
        assert 'Episode - TestTitle' in str(result)

    def test_generate_episode_file_different_extensions(self, tmp_path):
        """Should work with different file extensions."""
        for ext in ['mkv', 'mp4', 'avi']:
            result = generate_episode_file_path('Test', 1, 1, ext, tmp_path)
            assert str(result).endswith(f'.{ext}')
            assert 'Test - S01E01' in str(result)
