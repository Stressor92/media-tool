from __future__ import annotations

from pathlib import Path

from core.ebook.models import BookMetadata
from core.ebook.organization.library_organizer import LibraryOrganizer
from core.ebook.organization.naming_service import NamingService


def _metadata() -> BookMetadata:
    return BookMetadata(
        title="Leviathan Wakes",
        author="James S. A. Corey",
        series="The Expanse",
        series_index=1,
        published_year=2011,
        source="test",
    )


def test_library_organizer_dry_run_reports_target_path(tmp_path: Path) -> None:
    source = tmp_path / "input.epub"
    source.write_text("book", encoding="utf-8")
    organizer = LibraryOrganizer(NamingService(), dry_run=True)

    result = organizer.organize(source, _metadata(), library_root=tmp_path / "library")

    assert result.success is True
    assert result.action == "dry_run"
    assert result.new_path is not None
    assert "James S. A. Corey" in str(result.new_path)
    assert source.exists()


def test_library_organizer_moves_file_to_series_structure(tmp_path: Path) -> None:
    source = tmp_path / "input.epub"
    source.write_text("book", encoding="utf-8")
    organizer = LibraryOrganizer(NamingService(), dry_run=False)

    result = organizer.organize(source, _metadata(), library_root=tmp_path / "library")

    assert result.success is True
    assert result.action == "moved"
    assert result.new_path is not None
    assert result.new_path.exists()
    assert not source.exists()


def test_library_organizer_copy_mode_keeps_source(tmp_path: Path) -> None:
    source = tmp_path / "input.epub"
    source.write_text("book", encoding="utf-8")
    organizer = LibraryOrganizer(NamingService(), dry_run=False)

    result = organizer.organize(
        source,
        _metadata(),
        library_root=tmp_path / "library",
        copy_instead_of_move=True,
    )

    assert result.success is True
    assert result.action == "copied"
    assert source.exists()
    assert result.new_path is not None
    assert result.new_path.exists()
