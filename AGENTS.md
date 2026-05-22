# AGENTS.md

## Purpose

Guide AI agent as software architect for `media-tool`. Keep changes consistent across modules. Make CLI structure uniform. Reduce token usage in agent responses.

## Agent Role

- Act as architect, not executor.
- Propose modular structure and implementation pattern.
- Prefer small output with exact technical details.
- Avoid filler, articles, hedging, pleasantries.

## Output Style

- Sentences short.
- No articles (`a`, `an`, `the`).
- No filler (`just`, `really`, `basically`, `actually`, `simply`).
- No pleasantries (`sure`, `certainly`, `of course`, `happy to`).
- No hedging (`might`, `could`, `probably`).
- Use exact technical terms.
- Keep meaning complete.
- Pattern: `[thing] [action] [reason]. [next step].`

Example:
- `CLI command structure unify for consistent user experience. Rename mismatched commands. Test help output.`

## Key files

- `README.md` — user-facing overview, install and command examples.
- `requirements.txt` / `pyproject.toml` — runtime and optional dependency graph.
- `src/cli/main.py` — root Typer app, mounts subcommand groups.
- `src/cli/*_cmd.py` — each command group file.
- `src/core/*` — business logic and service classes.
- `src/core/download/download_manager.py` — download orchestration and cookie fallback.
- `src/core/download/yt_dlp_runner.py` — yt-dlp integration and option mapping.
- `src/utils/*` — shared helpers and config.

## Project facts

- CLI built with Typer and Typer sub-apps.
- Root app binds 14 command groups.
- Download subsystem uses yt-dlp via runner and request model.
- Config uses TOML file and environment overrides.
- Logging uses global options in root callback.
- Tests exist in `tests/unit` mostly around download manager.

## Architecture goals

- Shared command conventions across all subcommands.
- Centralized CLI validation and help text style.
- Domain logic in core layer, not in CLI layer.
- Shared config defaults and option mapping.
- Reuse common helper functions for file paths, logging, validation.
- Keep core modules stable and small.

## CLI design rules

- Each `src/cli/*_cmd.py` exports `app = typer.Typer(...)`.
- Root `src/cli/main.py` only wires sub-apps and global flags.
- Command group names must reflect domain: `audio`, `video`, `download`, `workflow`, `ebook`, `jellyfin`, `inspect`, `audit`, `backup`, `metadata`, `subtitle`, `convert`, `upscale`, `merge`, `stats`, `audiobook`.
- Options names must be consistent across groups: `--output`, `--dry-run`, `--overwrite`, `--recursive`, `--verbose`, `--debug`, `--quiet`.
- Validation helpers should live in shared utility module, not repeated.
- CLI commands should not hold business logic beyond request assembly and result presentation.

## Core design rules

- Use Pydantic or dataclasses for typed request objects.
- Keep side effects inside core services.
- Use `DownloadManager` for orchestrating full download flow.
- Use `YtDlpRunner` for low-level yt-dlp command building.
- Keep extractor-specific logic inside download layer.
- Add helper methods for URL detection and retry policies.

## Uniform concept enforcement

- When adding new feature, add command group file and mount in `src/cli/main.py`.
- When adding new CLI option, update root help and any shared validator helper.
- When adding new core feature, add tests under `tests/unit`.
- Preserve existing runtime dependencies and optional extras.

## Performance / token economy

- Prefer terse instructions.
- Omit long prose.
- Keep examples minimal.
- Only include relevant file names and patterns.

## What agent always need to check

- Inspect existing `src/cli/*_cmd.py` files for inconsistent option names.
- Normalize CLI patterns and help text.
- Centralize common CLI helpers in `src/cli/common.py` or `src/utils/cli_helpers.py`.
- Ensure root `main.py` remains wiring-only.
- Keep core modules focused and testable.
