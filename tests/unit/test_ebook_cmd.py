from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from cli.main import app
from utils.config import reset_config_cache


runner = CliRunner()


def test_ebook_group_prints_config_summary(tmp_path: Path, monkeypatch) -> None:
    config_path = tmp_path / "media-tool.toml"
    config_path.write_text(
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
    monkeypatch.setenv("MEDIA_TOOL_CONFIG", str(config_path))
    reset_config_cache()

    result = runner.invoke(app, ["ebook"])

    assert result.exit_code == 0
    assert "[ebook] active configuration" in result.stdout
    assert "metadata_providers: openlibrary, googlebooks" in result.stdout
    assert "conversion.target_format: epub" in result.stdout


def test_ebook_config_command_prints_summary(tmp_path: Path, monkeypatch) -> None:
    config_path = tmp_path / "media-tool.toml"
    config_path.write_text(
        """
[ebook]
preferred_format = "mobi"
download_cover = false
metadata_providers = ["googlebooks"]

[ebook.organization]
structure = "{author}/{title}"

[ebook.conversion]
target_format = "epub"
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setenv("MEDIA_TOOL_CONFIG", str(config_path))
    reset_config_cache()

    result = runner.invoke(app, ["ebook", "config"])

    assert result.exit_code == 0
    assert "preferred_format: mobi" in result.stdout
    assert "download_cover: False" in result.stdout
    assert "metadata_providers: googlebooks" in result.stdout
    assert "organization.structure: {author}/{title}" in result.stdout
