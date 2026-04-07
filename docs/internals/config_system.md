# Internal: Configuration System

## Scope

The configuration system is implemented in `src/utils/config.py` and provides a **typed, validated, cached application configuration** for the entire project.

Its job is to combine:

- built-in defaults
- TOML configuration files
- environment-variable overrides
- selected legacy environment mappings

into one `AppConfig` object.

---

## Configuration Model

The root object is `AppConfig`, a Pydantic model composed of smaller validated sections:

- `api`
- `tools`
- `paths`
- `defaults`
- `download`
- `jellyfin`
- `language_detection`
- `metadata`
- `ebook`
- `upscale`
- `statistics`
- `backup`

Each section uses `extra="forbid"` or similarly explicit validation so unexpected keys are caught early instead of silently ignored.

---

## Resolution Order

### File discovery

`find_config_file()` searches in the following order:

1. explicit `config_path` argument if provided
2. `MEDIA_TOOL_CONFIG` environment variable
3. `media-tool.toml` in the current working directory
4. `media-tool.toml` in the project root

If no file is found, the system still works from defaults plus environment overrides.

### Merge order

```text
defaults <- TOML file <- environment overrides
```

Environment overrides therefore take precedence over file content.

---

## Environment Override Model

The preferred naming scheme is:

```text
MEDIA_TOOL_<SECTION>__<FIELD>=...
```

Examples:

```text
MEDIA_TOOL_API__OPENSUBTITLES_API_KEY=...
MEDIA_TOOL_DOWNLOAD__SUBTITLE_LANGUAGES=de,en
MEDIA_TOOL_UPSCALE__ENCODER=nvenc
```

The loader also retains some legacy mappings such as:

- `OPENSUBTITLES_API_KEY -> api.opensubtitles_api_key`
- `TMDB_API_KEY -> api.tmdb_api_key`
- `FFMPEG_BIN -> tools.ffmpeg`
- `FFPROBE_BIN -> tools.ffprobe`

### Value parsing

The loader tries to coerce common types:

- booleans from `true` / `false`
- `null` / `none` to `None`
- JSON lists when present
- comma-separated lists for language/provider arrays

---

## Validation Strategy

Configuration validation is intentionally strict.

Examples visible in code:

- numeric bounds (`max_resolution`, confidence thresholds, timeout ranges)
- non-empty tool commands
- normalized language/provider lists
- constrained encoder choices (`auto`, `nvenc`, `amf`, `qsv`, `software`)

Invalid config raises `ConfigError` with a clear source description instead of silently continuing.

---

## Caching and Invalidation

`get_config()` caches the parsed `AppConfig` together with a cache key based on:

- the resolved config-file path, and
- relevant environment variables

`reset_config_cache()` is provided for explicit invalidation in tests or long-lived scenarios.

This keeps command startup fast while still respecting env-driven changes.

---

## Why this design?

The chosen design balances three needs:

1. **strong typing** for reliability
2. **portable configuration** through TOML files
3. **deployment flexibility** through environment overrides

The cost is a slightly more complex load path, but the result is much easier to reason about than scattered `os.getenv()` calls throughout the codebase.