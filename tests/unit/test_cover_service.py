from __future__ import annotations

from pathlib import Path

from core.ebook.cover.cover_selector import CoverSelector
from core.ebook.cover.cover_service import CoverService
from core.ebook.cover.providers.provider import CoverImage, CoverProvider
from core.ebook.models import BookMetadata
from tests.ebook_test_support import create_image_bytes, create_minimal_epub
from utils.epub_writer import EpubWriter


class FakeProvider(CoverProvider):
    def __init__(self, isbn_cover: CoverImage | None = None, title_covers: list[CoverImage] | None = None) -> None:
        self._isbn_cover = isbn_cover
        self._title_covers = title_covers or []

    def get_cover_by_isbn(self, isbn: str, size: str = "L") -> CoverImage | None:
        del isbn, size
        return self._isbn_cover

    def search_covers(self, title: str, author: str | None = None, limit: int = 3) -> list[CoverImage]:
        del title, author, limit
        return list(self._title_covers)

    def get_provider_name(self) -> str:
        return "fake"


def test_get_cover_selects_best_available_cover() -> None:
    low = CoverImage(create_image_bytes(400, 600), 400, 600, "jpeg", "fake", "low")
    high = CoverImage(create_image_bytes(1000, 1500), 1000, 1500, "jpeg", "fake", "high")
    metadata = BookMetadata(title="Dune", author="Frank Herbert", isbn13="9780441172719")
    service = CoverService([FakeProvider(isbn_cover=low), FakeProvider(isbn_cover=high)], CoverSelector(), EpubWriter())

    result = service.get_cover(metadata)

    assert result is not None
    assert result.width == 1000


def test_embed_and_export_cover_work_on_epub(tmp_path: Path) -> None:
    epub_path = tmp_path / "book.epub"
    create_minimal_epub(epub_path)
    cover = CoverImage(create_image_bytes(900, 1400), 900, 1400, "jpeg", "fake", "cover")
    service = CoverService([], CoverSelector(), EpubWriter())

    assert service.embed_cover(epub_path, cover, backup=True) is True
    assert epub_path.with_suffix(".epub.bak").exists()

    export_path = tmp_path / "cover.jpg"
    assert service.export_cover(cover, export_path) is True
    assert export_path.exists()