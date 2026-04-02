from __future__ import annotations

from pathlib import Path

from core.ebook.deduplication.duplicate_finder import DuplicateFinder
from core.ebook.deduplication.version_comparator import VersionComparator
from core.ebook.models import BookIdentity
from utils.fuzzy_matcher import FuzzyMatcher


class StubIdentifier:
    def identify(self, file_path: Path) -> BookIdentity:
        stem = file_path.stem.lower()
        if "isbn" in stem:
            return BookIdentity(title="Dune", author="Frank Herbert", isbn="9780441172719", isbn13="9780441172719")
        if "messiah" in stem:
            return BookIdentity(title="Dune Messiah", author="Frank Herbert")
        return BookIdentity(title="Dune", author="Frank Herbert")


class StubIsbnExtractor:
    def extract(self, file_path: Path) -> str | None:
        return "9780441172719" if "isbn" in file_path.stem.lower() else None


def test_version_comparator_prefers_epub(tmp_path: Path) -> None:
    epub = tmp_path / "book.epub"
    pdf = tmp_path / "book.pdf"
    mobi = tmp_path / "book.mobi"
    epub.write_bytes(b"x" * 500)
    pdf.write_bytes(b"x" * 500)
    mobi.write_bytes(b"x" * 500)

    comparator = VersionComparator()
    best = comparator.select_best([pdf, mobi, epub])
    assert best == epub


def test_duplicate_finder_groups_by_isbn_and_selects_best(tmp_path: Path) -> None:
    library = tmp_path / "library"
    library.mkdir()

    a = library / "dune-isbn.epub"
    b = library / "dune-isbn.mobi"
    c = library / "dune-messiah.epub"
    a.write_bytes(b"a")
    b.write_bytes(b"b")
    c.write_bytes(b"c")

    finder = DuplicateFinder(
        isbn_extractor=StubIsbnExtractor(),
        book_identifier=StubIdentifier(),
        version_comparator=VersionComparator(),
        fuzzy_matcher=FuzzyMatcher(),
    )

    groups = finder.find_duplicates(library)

    assert len(groups) == 1
    group = groups[0]
    assert set(group.books) == {a, b}
    assert group.best_version == a
    assert group.match_confidence >= 0.95
