from __future__ import annotations

from pathlib import Path
from typing import cast

from core.ebook.conversion.conversion_profiles import ConversionProfiles
from core.ebook.conversion.format_converter import FormatConverter
from core.ebook.models import EbookFormat
from utils.calibre_runner import CalibreRunner


class FakeCalibreRunner:
    def __init__(self) -> None:
        self.calls: list[tuple[Path, Path, list[str] | None, int]] = []

    def convert(self, input_path: Path, output_path: Path, extra_args: list[str] | None = None, timeout: int = 600):
        self.calls.append((input_path, output_path, extra_args, timeout))
        output_path.write_bytes(input_path.read_bytes() + b"\nconverted")
        return None


def test_format_converter_dry_run_creates_planned_paths_and_backup(tmp_path: Path) -> None:
    source = tmp_path / "book.epub"
    source.write_bytes(b"epub")
    runner = FakeCalibreRunner()
    converter = FormatConverter(cast(CalibreRunner, runner), dry_run=True)

    result = converter.convert(source, EbookFormat.MOBI, create_backup=True)

    assert result.success is True
    assert result.dry_run is True
    assert result.output_path == tmp_path / "book.mobi"
    assert result.backup_path == tmp_path / "book.epub.pre-convert.bak"
    assert not result.output_path.exists()
    assert len(runner.calls) == 0


def test_format_converter_executes_conversion_with_profile(tmp_path: Path) -> None:
    source = tmp_path / "book.epub"
    source.write_bytes(b"epub")
    runner = FakeCalibreRunner()
    converter = FormatConverter(cast(CalibreRunner, runner), dry_run=False)

    result = converter.convert(
        source,
        EbookFormat.AZW3,
        profile=ConversionProfiles.KINDLE_HIGH_QUALITY,
        create_backup=True,
    )

    assert result.success is True
    assert result.output_path == tmp_path / "book.azw3"
    assert result.output_path.exists()
    assert result.backup_path == tmp_path / "book.epub.pre-convert.bak"
    assert result.backup_path.exists()
    assert runner.calls
    _input, _output, args, _timeout = runner.calls[0]
    assert args is not None
    assert "--output-profile" in args
