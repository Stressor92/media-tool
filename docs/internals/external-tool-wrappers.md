# Internals: External Tool Wrappers

## Scope

Wrapper modules encapsulate subprocess interactions for ffmpeg, ffprobe, and yt-dlp.

## Wrappers

- `utils.ffmpeg_runner`
- `utils.ffprobe_runner`
- `utils.ytdlp_runner`

## Responsibilities

- Build executable command arguments
- Execute subprocess with controlled capture/error handling
- Return structured success/error output models

## Why Wrappers Exist

Without wrappers, subprocess logic would be duplicated across many domain modules. Wrappers centralize process concerns and keep domain code focused on media semantics.

## Error Handling Pattern

Wrappers surface non-zero exit results as rich failure objects rather than raw exceptions in most operational paths. Callers decide retry, fallback, or abort behavior.

## Trade-offs

Positive:

- Consistent process behavior and logging
- Easier to test command construction paths

Negative:

- Domain modules still need to understand tool-specific constraints
- Wrapper abstraction cannot hide all backend variability
