from __future__ import annotations

from pathlib import Path
import zipfile

from core.ebook.cover.cover_selector import CoverSelector
from core.ebook.cover.cover_service import CoverService
from core.ebook.cover.providers.provider import CoverImage
from core.ebook.models import BookMetadata
from core.ebook.normalization import EpubValidator, EbookNormalizer, MetadataEmbedder, TocGenerator
from tests.ebook_test_support import create_image_bytes, create_minimal_epub
from utils.epub_reader import EpubReader
from utils.epub_writer import EpubWriter


def test_normalize_updates_metadata_cover_and_toc(tmp_path: Path) -> None:
    epub_path = tmp_path / "workflow.epub"
    create_minimal_epub(epub_path)

    metadata = BookMetadata(
        title="Dune",
        author="Frank Herbert",
        description="Epic science fiction novel with enough words for metadata completeness.",
        publisher="Chilton Books",
        published_year=1965,
        isbn13="9780441172719",
        source="openlibrary",
    )
    cover = CoverImage(create_image_bytes(1000, 1500), 1000, 1500, "jpeg", "test", "memory")

    writer = EpubWriter()
    normalizer = EbookNormalizer(
        metadata_embedder=MetadataEmbedder(writer),
        cover_service=CoverService([], CoverSelector(), writer),
        toc_generator=TocGenerator(writer),
        epub_validator=EpubValidator(EpubReader()),
    )

    result = normalizer.normalize(epub_path, metadata=metadata, cover=cover, fix_toc=True, backup=True)

    assert result.success is True
    assert result.metadata_updated is True
    assert result.cover_embedded is True
    assert result.toc_generated is True
    assert epub_path.with_suffix(".epub.bak").exists()

    updated = EpubReader().get_metadata(epub_path)
    assert updated["title"] == "Dune"
    assert updated["author"] == "Frank Herbert"
    assert updated["publisher"] == "Chilton Books"

    with zipfile.ZipFile(epub_path, "r") as archive:
        names = set(archive.namelist())
        assert "OEBPS/images/cover.jpg" in names
        assert "OEBPS/nav.xhtml" in names