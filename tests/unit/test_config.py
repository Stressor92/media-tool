from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from utils.config import ConfigError, build_missing_config_hint, get_config, reset_config_cache
from utils.ffmpeg_runner import run_ffmpeg
from utils.ffprobe_runner import probe_file


@pytest.fixture(autouse=True)
def clear_config_cache(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    for key in [
        "MEDIA_TOOL_CONFIG",
        "MEDIA_TOOL_API__OPENSUBTITLES_API_KEY",
        "MEDIA_TOOL_API__GOOGLEBOOKS_API_KEY",
        "MEDIA_TOOL_DEFAULTS__SUBTITLES__LANGUAGES",
        "OPENSUBTITLES_API_KEY",
        "GOOGLEBOOKS_API_KEY",
        "FFMPEG_BIN",
        "FFPROBE_BIN",
    ]:
        monkeypatch.delenv(key, raising=False)
    reset_config_cache()
    yield
    reset_config_cache()


def test_get_config_uses_defaults_when_file_missing(tmp_path: Path) -> None:
    config = get_config(tmp_path / "missing.toml")

    assert config.tools.ffmpeg == "ffmpeg"
    assert config.tools.ffprobe == "ffprobe"
    assert config.tools.yt_dlp == "yt-dlp"
    assert config.defaults.subtitles.languages == ["en"]
    assert config.api.opensubtitles_api_key is None
    assert config.api.googlebooks_api_key is None
    assert config.ebook.preferred_format == "epub"
    assert config.ebook.download_cover is True
    assert config.ebook.metadata_providers == ["openlibrary", "googlebooks"]
    assert config.ebook.organization.structure == "{author}/{series}/{title}"
    assert config.ebook.conversion.target_format == "epub"


def test_get_config_reads_file_and_env_overrides(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_path = tmp_path / "media-tool.toml"
    config_path.write_text(
        """
[api]
opensubtitles_api_key = "from-file"
googlebooks_api_key = "from-file-google"

[tools]
ffmpeg = "C:/tools/ffmpeg.exe"
yt_dlp = "C:/tools/yt-dlp.exe"

[defaults.subtitles]
languages = ["en", "de"]

[ebook]
preferred_format = "mobi"
download_cover = false
metadata_providers = ["googlebooks"]

[ebook.organization]
structure = "{author}/{title}"

[ebook.conversion]
target_format = "mobi"
""".strip(),
        encoding="utf-8",
    )

    monkeypatch.setenv("MEDIA_TOOL_CONFIG", str(config_path))
    monkeypatch.setenv("MEDIA_TOOL_API__OPENSUBTITLES_API_KEY", "from-env")
    monkeypatch.setenv("MEDIA_TOOL_API__GOOGLEBOOKS_API_KEY", "from-env-google")
    monkeypatch.setenv("MEDIA_TOOL_DEFAULTS__SUBTITLES__LANGUAGES", "de,fr")
    monkeypatch.setenv("MEDIA_TOOL_EBOOK__METADATA_PROVIDERS", "openlibrary,googlebooks")

    config = get_config()

    assert config.api.opensubtitles_api_key == "from-env"
    assert config.api.googlebooks_api_key == "from-env-google"
    assert config.tools.ffmpeg == "C:/tools/ffmpeg.exe"
    assert config.tools.yt_dlp == "C:/tools/yt-dlp.exe"
    assert config.defaults.subtitles.languages == ["de", "fr"]
    assert config.ebook.preferred_format == "mobi"
    assert config.ebook.download_cover is False
    assert config.ebook.metadata_providers == ["openlibrary", "googlebooks"]
    assert config.ebook.organization.structure == "{author}/{title}"
    assert config.ebook.conversion.target_format == "mobi"


def test_get_config_supports_legacy_environment_variables(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENSUBTITLES_API_KEY", "legacy-key")
    monkeypatch.setenv("GOOGLEBOOKS_API_KEY", "legacy-google-key")
    monkeypatch.setenv("FFMPEG_BIN", "D:/portable/ffmpeg.exe")

    config = get_config()

    assert config.api.opensubtitles_api_key == "legacy-key"
    assert config.api.googlebooks_api_key == "legacy-google-key"
    assert config.tools.ffmpeg == "D:/portable/ffmpeg.exe"


def test_get_config_invalid_toml_raises_config_error(tmp_path: Path) -> None:
    config_path = tmp_path / "media-tool.toml"
    config_path.write_text("[api\nopensubtitles_api_key = 'broken'", encoding="utf-8")

    with pytest.raises(ConfigError):
        get_config(config_path)


def test_missing_config_hint_mentions_expected_setup() -> None:
    hint = build_missing_config_hint()

    assert "media-tool.toml" in hint
    assert "media-tool.example.toml" in hint
    assert "MEDIA_TOOL_CONFIG" in hint


def test_run_ffmpeg_uses_configured_binary(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_path = tmp_path / "media-tool.toml"
    config_path.write_text(
        """
[tools]
ffmpeg = "C:/custom/ffmpeg.exe"
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setenv("MEDIA_TOOL_CONFIG", str(config_path))

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stderr=b"", stdout=b"")

        result = run_ffmpeg(["-version"])

    assert result.command[0] == "C:/custom/ffmpeg.exe"


def test_probe_file_uses_configured_binary(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_path = tmp_path / "media-tool.toml"
    config_path.write_text(
        """
[tools]
ffprobe = "C:/custom/ffprobe.exe"
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setenv("MEDIA_TOOL_CONFIG", str(config_path))

    media_path = tmp_path / "sample.mkv"
    media_path.write_bytes(b"fake")

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=0,
            stderr=b"",
            stdout=b'{"streams": [], "format": {}}',
        )

        result = probe_file(media_path)

    assert result.success is True
    assert mock_run.call_args.args[0][0] == "C:/custom/ffprobe.exe"
