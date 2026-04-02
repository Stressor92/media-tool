from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from core.ebook.conversion.format_converter import FormatConverter
from core.ebook.models import EbookFormat
from tests.ebook_test_support import create_minimal_epub
from utils.calibre_runner import CalibreRunner

pytestmark = [pytest.mark.integration, pytest.mark.external]


def test_real_calibre_epub_to_mobi_conversion(tmp_path: Path) -> None:
    if shutil.which("ebook-convert") is None:
        pytest.skip("Calibre ebook-convert is not installed")

    source = tmp_path / "book.epub"
    create_minimal_epub(source, title="Integration Book", author="Integration Author")

    converter = FormatConverter(CalibreRunner())
    result = converter.convert(source, EbookFormat.MOBI, create_backup=False)

    assert result.success is True
    assert result.output_path is not None
    assert result.output_path.exists()
