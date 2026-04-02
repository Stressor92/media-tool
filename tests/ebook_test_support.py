from __future__ import annotations

import zipfile
from io import BytesIO
from pathlib import Path

from PIL import Image


def create_image_bytes(
    width: int = 900,
    height: int = 1400,
    color: tuple[int, int, int] = (120, 40, 30),
    image_format: str = "JPEG",
) -> bytes:
    """Create an in-memory test image."""
    output = BytesIO()
    Image.new("RGB", (width, height), color).save(output, format=image_format)
    return output.getvalue()


def create_minimal_epub(epub_path: Path, title: str = "Original Title", author: str = "Original Author") -> None:
    """Create a tiny but structurally valid EPUB for tests."""
    opf = f"""<?xml version='1.0' encoding='utf-8'?>
    <package xmlns='http://www.idpf.org/2007/opf' version='3.0' unique-identifier='bookid'>
      <metadata xmlns:dc='http://purl.org/dc/elements/1.1/'>
        <dc:title>{title}</dc:title>
        <dc:creator>{author}</dc:creator>
        <dc:identifier id='bookid'>9780306406157</dc:identifier>
        <dc:language>en</dc:language>
      </metadata>
      <manifest>
        <item id='chapter1' href='chapter1.xhtml' media-type='application/xhtml+xml'/>
      </manifest>
      <spine>
        <itemref idref='chapter1'/>
      </spine>
    </package>
    """
    chapter = """<?xml version='1.0' encoding='utf-8'?>
    <html xmlns='http://www.w3.org/1999/xhtml'><head><title>Chapter 1</title></head><body><h1>Chapter 1</h1></body></html>
    """
    container = """<?xml version='1.0'?>
    <container version='1.0' xmlns='urn:oasis:names:tc:opendocument:xmlns:container'>
      <rootfiles>
        <rootfile full-path='OEBPS/content.opf' media-type='application/oebps-package+xml'/>
      </rootfiles>
    </container>
    """
    with zipfile.ZipFile(epub_path, "w") as archive:
        archive.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        archive.writestr("META-INF/container.xml", container)
        archive.writestr("OEBPS/content.opf", opf)
        archive.writestr("OEBPS/chapter1.xhtml", chapter)
