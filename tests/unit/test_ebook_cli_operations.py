from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from cli.main import app
from core.ebook.models import AuditReport, DuplicateGroup
from utils.config import reset_config_cache


runner = CliRunner()


class _Bundle:
    def __init__(self) -> None:
        self.identifier = object()
        self.metadata_service = object()
        self.cover_service = object()
        self.normalizer = object()
        self.isbn_extractor = object()
        self.fuzzy_matcher = object()


def _write_config(path: Path) -> None:
    path.write_text(
        """
[ebook]
preferred_format = "epub"
download_cover = true
metadata_providers = ["openlibrary", "googlebooks"]

[ebook.organization]
structure = "{author}/{series}/{title}"

[ebook.conversion]
target_format = "epub"
""".strip(),
        encoding="utf-8",
    )


def test_ebook_audit_command_with_stubbed_auditor(tmp_path: Path, monkeypatch) -> None:
    cfg = tmp_path / 'media-tool.toml'
    _write_config(cfg)
    monkeypatch.setenv('MEDIA_TOOL_CONFIG', str(cfg))
    reset_config_cache()

    library = tmp_path / 'library'
    library.mkdir()

    monkeypatch.setattr('cli.ebook_cmd._build_services', lambda: _Bundle())

    class _Auditor:
        def __init__(self, **kwargs):
            pass

        def audit(self, library_path: Path, recursive: bool = True, check_covers: bool = True, check_series: bool = True) -> AuditReport:
            return AuditReport(total_books=1, total_size_gb=0.01)

    monkeypatch.setattr('cli.ebook_cmd.LibraryAuditor', _Auditor)

    result = runner.invoke(app, ['ebook', 'audit', str(library)])
    assert result.exit_code == 0
    assert 'Library Audit Report' in result.stdout


def test_ebook_deduplicate_command_dry_run(tmp_path: Path, monkeypatch) -> None:
    cfg = tmp_path / 'media-tool.toml'
    _write_config(cfg)
    monkeypatch.setenv('MEDIA_TOOL_CONFIG', str(cfg))
    reset_config_cache()

    library = tmp_path / 'library'
    library.mkdir()
    keep = library / 'book.epub'
    remove = library / 'book.mobi'
    keep.write_text('x', encoding='utf-8')
    remove.write_text('y', encoding='utf-8')

    monkeypatch.setattr('cli.ebook_cmd._build_services', lambda: _Bundle())

    class _Finder:
        def __init__(self, **kwargs):
            pass

        def find_duplicates(self, library_path: Path, recursive: bool = True):
            return [DuplicateGroup(books=[keep, remove], match_confidence=0.95, best_version=keep, reason='EPUB best')]

    monkeypatch.setattr('cli.ebook_cmd.DuplicateFinder', _Finder)

    result = runner.invoke(app, ['ebook', 'deduplicate', str(library), '--dry-run'])
    assert result.exit_code == 0
    assert 'Duplicate Group' in result.stdout


def test_ebook_convert_command_dry_run(tmp_path: Path, monkeypatch) -> None:
    cfg = tmp_path / 'media-tool.toml'
    _write_config(cfg)
    monkeypatch.setenv('MEDIA_TOOL_CONFIG', str(cfg))
    reset_config_cache()

    source = tmp_path / 'book.epub'
    source.write_text('x', encoding='utf-8')

    class _Calibre:
        pass

    class _Result:
        def __init__(self, success: bool) -> None:
            self.success = success

    class _Converter:
        def __init__(self, calibre_runner, dry_run: bool = False):
            self.dry_run = dry_run

        def convert(self, **kwargs):
            return _Result(True)

    monkeypatch.setattr('cli.ebook_cmd.CalibreRunner', lambda: _Calibre())
    monkeypatch.setattr('cli.ebook_cmd.FormatConverter', _Converter)

    result = runner.invoke(app, ['ebook', 'convert', str(source), 'mobi', '--dry-run'])
    assert result.exit_code == 0
    assert 'Conversion complete' in result.stdout
