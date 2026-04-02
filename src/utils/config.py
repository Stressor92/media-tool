"""Typed application configuration loader for media-tool."""

from __future__ import annotations

import json
import os
import tomllib
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

CONFIG_FILE_NAME = "media-tool.toml"
EXAMPLE_CONFIG_FILE_NAME = "media-tool.example.toml"
ENV_PREFIX = "MEDIA_TOOL_"


class ConfigError(RuntimeError):
    """Raised when configuration loading or validation fails."""


class ApiConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    opensubtitles_api_key: str | None = None
    acoustid_api_key: str | None = None
    tmdb_api_key: str | None = None
    opensubtitles_user_agent: str = "media-tool v1.0"

    @field_validator("opensubtitles_api_key", "acoustid_api_key", "tmdb_api_key", mode="before")
    @classmethod
    def _normalize_optional_secret(cls, value: object) -> object:
        if value is None:
            return None
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value

    @field_validator("opensubtitles_user_agent")
    @classmethod
    def _validate_user_agent(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("opensubtitles_user_agent must not be empty")
        return normalized


class ToolConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ffmpeg: str = "ffmpeg"
    ffprobe: str = "ffprobe"
    yt_dlp: str = "yt-dlp"

    @field_validator("ffmpeg", "ffprobe", "yt_dlp")
    @classmethod
    def _validate_tool_command(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("tool command must not be empty")
        return normalized


class PathConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    library_root: Path | None = None
    incoming_root: Path | None = None
    temp_dir: Path | None = None

    @field_validator("library_root", "incoming_root", "temp_dir", mode="before")
    @classmethod
    def _normalize_optional_path(cls, value: object) -> object:
        if value is None:
            return None
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return None
            return Path(stripped).expanduser()
        return value


class SubtitleDefaults(BaseModel):
    model_config = ConfigDict(extra="forbid")

    languages: list[str] = Field(default_factory=lambda: ["en"])
    embed: bool = True
    auto: bool = True

    @field_validator("languages")
    @classmethod
    def _normalize_languages(cls, value: list[str]) -> list[str]:
        normalized = [item.strip().lower() for item in value if item.strip()]
        if not normalized:
            raise ValueError("defaults.subtitles.languages must contain at least one language")
        return normalized


class AudioDefaults(BaseModel):
    model_config = ConfigDict(extra="forbid")

    min_confidence: float = Field(default=0.7, ge=0.0, le=1.0)


class LanguageDetectionConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    min_confidence: float = Field(default=0.85, ge=0.0, le=1.0)
    whisper_model: str = "medium"
    device: str = "auto"
    sample_duration: int = Field(default=30, ge=1)
    sample_offset: int = Field(default=120, ge=0)
    create_backup: bool = False
    hint_languages: list[str] = Field(default_factory=lambda: ["de", "en"])

    @field_validator("whisper_model", "device", mode="before")
    @classmethod
    def _normalize_non_empty(cls, value: object) -> object:
        if isinstance(value, str):
            normalized = value.strip()
            if not normalized:
                raise ValueError("field must not be empty")
            return normalized
        return value

    @field_validator("hint_languages")
    @classmethod
    def _normalize_hint_languages(cls, value: list[str]) -> list[str]:
        return [item.strip().lower() for item in value if item.strip()]


class MetadataArtworkConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    download_poster: bool = True
    download_fanart: bool = True
    download_banner: bool = False
    download_thumb: bool = False
    download_logo: bool = False


class MetadataCastConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_actors: int = Field(default=20, ge=1, le=100)


class MetadataConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    language: str = "de-DE"
    fallback_language: str = "en-US"
    preferred_artwork_lang: str = "de"
    auto_select: bool = True
    overwrite_nfo: bool = False
    overwrite_artwork: bool = False
    artwork: MetadataArtworkConfig = Field(default_factory=MetadataArtworkConfig)
    cast: MetadataCastConfig = Field(default_factory=MetadataCastConfig)

    @field_validator("language", "fallback_language", "preferred_artwork_lang", mode="before")
    @classmethod
    def _normalize_metadata_strings(cls, value: object) -> object:
        if isinstance(value, str):
            normalized = value.strip()
            if not normalized:
                raise ValueError("metadata field must not be empty")
            return normalized
        return value


class EbookOrganizationConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    structure: str = "{author}/{series}/{title}"

    @field_validator("structure")
    @classmethod
    def _validate_structure(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("ebook.organization.structure must not be empty")
        return normalized


class EbookConversionConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_format: str = "epub"

    @field_validator("target_format")
    @classmethod
    def _validate_target_format(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not normalized:
            raise ValueError("ebook.conversion.target_format must not be empty")
        return normalized


class EbookConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    preferred_format: str = "epub"
    download_cover: bool = True
    metadata_providers: list[str] = Field(default_factory=lambda: ["openlibrary", "googlebooks"])
    organization: EbookOrganizationConfig = Field(default_factory=EbookOrganizationConfig)
    conversion: EbookConversionConfig = Field(default_factory=EbookConversionConfig)

    @field_validator("preferred_format")
    @classmethod
    def _validate_preferred_format(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not normalized:
            raise ValueError("ebook.preferred_format must not be empty")
        return normalized

    @field_validator("metadata_providers")
    @classmethod
    def _normalize_metadata_providers(cls, value: list[str]) -> list[str]:
        normalized = [item.strip().lower() for item in value if item.strip()]
        if not normalized:
            raise ValueError("ebook.metadata_providers must contain at least one provider")
        return normalized


class DefaultConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subtitles: SubtitleDefaults = Field(default_factory=SubtitleDefaults)
    audio: AudioDefaults = Field(default_factory=AudioDefaults)


class DownloadConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    default_output_video: str = "downloads/videos"
    default_output_music: str = "downloads/music"
    default_output_series: str = "downloads/series"
    max_resolution: int = Field(default=1080, ge=144, le=4320)
    audio_format: str = "mp3"
    audio_quality: str = "320k"
    preferred_language: str = "de"
    subtitle_languages: list[str] = Field(default_factory=lambda: ["de", "en"])
    embed_subtitles: bool = True
    embed_thumbnail: bool = True
    sponsorblock_remove: list[str] = Field(default_factory=lambda: ["sponsor"])

    @field_validator(
        "default_output_video",
        "default_output_music",
        "default_output_series",
        "audio_format",
        "audio_quality",
        "preferred_language",
        mode="before",
    )
    @classmethod
    def _normalize_non_empty_strings(cls, value: object) -> object:
        if isinstance(value, str):
            normalized = value.strip()
            if not normalized:
                raise ValueError("download field must not be empty")
            return normalized
        return value

    @field_validator("subtitle_languages", "sponsorblock_remove")
    @classmethod
    def _normalize_string_lists(cls, value: list[str]) -> list[str]:
        normalized = [item.strip().lower() for item in value if item.strip()]
        return normalized


class JellyfinConfig(BaseModel):
    model_config = ConfigDict(extra="allow")

    base_url: str = ""
    api_key: str | None = None
    wait_for_scan: bool = False
    scan_timeout: int = Field(default=300, ge=10)

    @field_validator("api_key", mode="before")
    @classmethod
    def _normalize_api_key(cls, value: object) -> object:
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value


class AppConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    api: ApiConfig = Field(default_factory=ApiConfig)
    tools: ToolConfig = Field(default_factory=ToolConfig)
    paths: PathConfig = Field(default_factory=PathConfig)
    defaults: DefaultConfig = Field(default_factory=DefaultConfig)
    download: DownloadConfig = Field(default_factory=DownloadConfig)
    jellyfin: JellyfinConfig = Field(default_factory=lambda: JellyfinConfig())
    language_detection: LanguageDetectionConfig = Field(default_factory=LanguageDetectionConfig)
    metadata: MetadataConfig = Field(default_factory=MetadataConfig)
    ebook: EbookConfig = Field(default_factory=EbookConfig)


_CONFIG_CACHE: AppConfig | None = None
_CONFIG_CACHE_KEY: tuple[str | None, tuple[tuple[str, str], ...]] | None = None


def get_project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def get_default_config_path() -> Path:
    return Path.cwd() / CONFIG_FILE_NAME


def get_example_config_path() -> Path:
    return get_project_root() / EXAMPLE_CONFIG_FILE_NAME


def find_config_file(config_path: str | Path | None = None) -> Path | None:
    if config_path is not None:
        explicit = Path(config_path).expanduser()
        return explicit if explicit.exists() else None

    env_path = os.getenv(f"{ENV_PREFIX}CONFIG")
    candidates: list[Path] = []
    if env_path:
        candidates.append(Path(env_path).expanduser())

    cwd_candidate = get_default_config_path()
    candidates.append(cwd_candidate)

    repo_candidate = get_project_root() / CONFIG_FILE_NAME
    if repo_candidate != cwd_candidate:
        candidates.append(repo_candidate)

    for candidate in candidates:
        if candidate.exists():
            return candidate

    return None


def has_config_file(config_path: str | Path | None = None) -> bool:
    return find_config_file(config_path) is not None


def reset_config_cache() -> None:
    global _CONFIG_CACHE, _CONFIG_CACHE_KEY
    _CONFIG_CACHE = None
    _CONFIG_CACHE_KEY = None


def build_missing_config_hint() -> str:
    default_path = get_default_config_path()
    return (
        f"Create {default_path} from {EXAMPLE_CONFIG_FILE_NAME}, or set "
        f"{ENV_PREFIX}CONFIG to a custom file. You can also override individual settings "
        f"with env vars such as {ENV_PREFIX}API__OPENSUBTITLES_API_KEY."
    )


def get_config(config_path: str | Path | None = None) -> AppConfig:
    global _CONFIG_CACHE, _CONFIG_CACHE_KEY

    resolved_path = find_config_file(config_path)
    cache_key = _build_cache_key(resolved_path)
    if _CONFIG_CACHE is not None and _CONFIG_CACHE_KEY == cache_key:
        return _CONFIG_CACHE

    config = _load_config(resolved_path)
    _CONFIG_CACHE = config
    _CONFIG_CACHE_KEY = cache_key
    return config


def _build_cache_key(config_path: Path | None) -> tuple[str | None, tuple[tuple[str, str], ...]]:
    normalized_path = str(config_path.resolve()) if config_path is not None else None
    env_items = tuple(sorted((key, value) for key, value in os.environ.items() if _is_relevant_env_var(key)))
    return normalized_path, env_items


def _load_config(config_path: Path | None) -> AppConfig:
    raw_config: dict[str, Any] = {}

    if config_path is not None:
        try:
            with config_path.open("rb") as handle:
                parsed = tomllib.load(handle)
        except tomllib.TOMLDecodeError as exc:
            raise ConfigError(f"Invalid TOML in {config_path}: {exc}") from exc
        except OSError as exc:
            raise ConfigError(f"Unable to read config file {config_path}: {exc}") from exc

        if not isinstance(parsed, dict):
            raise ConfigError(f"Config file {config_path} must contain a TOML table at the top level")
        raw_config = parsed

    merged = _deep_merge(raw_config, _env_overrides())

    try:
        return AppConfig.model_validate(merged)
    except ValidationError as exc:
        source = str(config_path) if config_path is not None else "defaults and environment"
        raise ConfigError(f"Invalid media-tool configuration from {source}: {exc}") from exc


def _env_overrides() -> dict[str, Any]:
    overrides: dict[str, Any] = {}

    for key, value in os.environ.items():
        # Skip config and test gate variables
        if key in (f"{ENV_PREFIX}CONFIG", "MEDIA_TOOL_INTEGRATION_TESTS"):
            continue

        mapped_path = _legacy_env_mapping(key)
        if mapped_path is None and key.startswith(ENV_PREFIX):
            mapped_path = [segment.lower() for segment in key[len(ENV_PREFIX) :].split("__") if segment]

        if not mapped_path:
            continue

        _insert_nested_value(overrides, mapped_path, _parse_env_value(mapped_path[-1], value))

    return overrides


def _legacy_env_mapping(key: str) -> list[str] | None:
    mapping = {
        "OPENSUBTITLES_API_KEY": ["api", "opensubtitles_api_key"],
        "ACOUSTID_API_KEY": ["api", "acoustid_api_key"],
        "TMDB_API_KEY": ["api", "tmdb_api_key"],
        "FFMPEG_BIN": ["tools", "ffmpeg"],
        "FFPROBE_BIN": ["tools", "ffprobe"],
    }
    return mapping.get(key)


def _parse_env_value(field_name: str, value: str) -> Any:
    normalized = value.strip()

    if field_name in {"languages", "subtitle_languages", "sponsorblock_remove", "metadata_providers"}:
        if normalized.startswith("["):
            try:
                parsed = json.loads(normalized)
            except json.JSONDecodeError:
                parsed = None
            if isinstance(parsed, list):
                return [str(item) for item in parsed]
        return [item.strip() for item in normalized.split(",") if item.strip()]

    lowered = normalized.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    if lowered == "none" or lowered == "null":
        return None

    try:
        return json.loads(normalized)
    except json.JSONDecodeError:
        return normalized


def _insert_nested_value(target: dict[str, Any], path: list[str], value: Any) -> None:
    current = target
    for segment in path[:-1]:
        next_value = current.get(segment)
        if not isinstance(next_value, dict):
            next_value = {}
            current[segment] = next_value
        current = next_value
    current[path[-1]] = value


def _deep_merge(base: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = dict(base)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _is_relevant_env_var(key: str) -> bool:
    return key.startswith(ENV_PREFIX) or key in {
        "OPENSUBTITLES_API_KEY",
        "ACOUSTID_API_KEY",
        "TMDB_API_KEY",
        "FFMPEG_BIN",
        "FFPROBE_BIN",
    }
