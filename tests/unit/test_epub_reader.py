from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from utils.epub_reader import EpubReader, EpubReadError


def _write_epub(epub_path: Path, opf_content: str) -> None:
    with zipfile.ZipFile(epub_path, "w") as archive:
        archive.writestr(
            "META-INF/container.xml",
            """<?xml version='1.0'?>
            <container version='1.0' xmlns='urn:oasis:names:tc:opendocument:xmlns:container'>
              <rootfiles>
                <rootfile full-path='OEBPS/content.opf' media-type='application/oebps-package+xml'/>
              </rootfiles>
            </container>
            """,
        )
        archive.writestr("OEBPS/content.opf", opf_content)


def test_get_metadata_reads_standard_epub_fields(tmp_path: Path) -> None:
    epub_path = tmp_path / "sample.epub"
    _write_epub(
        epub_path,
        """<?xml version='1.0' encoding='utf-8'?>
        <package xmlns:dc='http://purl.org/dc/elements/1.1/'>
          <metadata>
            <dc:title>Example Book</dc:title>
            <dc:creator>Jane Doe</dc:creator>
            <dc:description>Book description</dc:description>
            <dc:identifier>9780306406157</dc:identifier>
            <dc:publisher>Acme Press</dc:publisher>
            <dc:date>2024-04-01</dc:date>
            <dc:language>en</dc:language>
          </metadata>
        </package>
        """,
    )

    metadata = EpubReader().get_metadata(epub_path)

    assert metadata["title"] == "Example Book"
    assert metadata["author"] == "Jane Doe"
    assert metadata["identifier"] == "9780306406157"
    assert metadata["language"] == "en"


def test_get_metadata_raises_read_error_for_invalid_zip(tmp_path: Path) -> None:
    epub_path = tmp_path / "broken.epub"
    epub_path.write_text("not-a-zip", encoding="utf-8")

    with pytest.raises(EpubReadError):
        EpubReader().get_metadata(epub_path)
