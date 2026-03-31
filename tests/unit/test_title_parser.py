from pathlib import Path

import pytest

from core.metadata.title_parser import _clean_title, parse_title


@pytest.mark.parametrize(
    "filename,expected_title,expected_year",
    [
        ("Inception (2010).mkv", "Inception", 2010),
        ("Inception.2010.BluRay.1080p.mkv", "Inception", 2010),
        ("The.Dark.Knight.2008.mkv", "The Dark Knight", 2008),
        ("Inception [2010].mkv", "Inception", 2010),
        ("No Year Film.mkv", "No Year Film", None),
        ("2001.A.Space.Odyssey.1968.mkv", "2001 A Space Odyssey", 1968),
    ],
)
def test_parse_various_filenames(
    filename: str,
    expected_title: str,
    expected_year: int | None,
) -> None:
    path = Path(f"/media/{filename}")
    result = parse_title(path)
    assert result.title == expected_title
    assert result.year == expected_year


def test_prefers_folder_over_filename() -> None:
    path = Path("/media/Inception (2010)/Inception.2010.BluRay.mkv")
    result = parse_title(path)
    assert result.title == "Inception"
    assert result.year == 2010


def test_clean_title_removes_quality_tags() -> None:
    assert _clean_title("Inception.BluRay.1080p.x265") == "Inception"
    assert _clean_title("Film German HEVC") == "Film"
