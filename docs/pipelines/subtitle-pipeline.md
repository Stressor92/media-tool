# Subtitle Pipeline

## Objective

Acquire and optionally translate subtitles while preserving timing and format integrity.

## Pipeline Steps

1. Input analysis
2. Provider query and candidate retrieval
3. Best candidate selection and download
4. Optional translation backend selection
5. Chunked translation
6. Subtitle reconstruction and output write

## Provider Phase

The downloader uses provider abstraction with OpenSubtitles as a concrete implementation in this codebase.

Behaviors:

- Handles API/network errors with retry and structured failure output
- May return no subtitle without aborting broader workflow

## Translation Phase

Translation uses backend abstraction (`translator_protocol`, `translator_factory`).

Responsibilities:

- Choose backend based on config/runtime availability
- Chunk input to backend-safe units
- Preserve subtitle ordering and structural tokens

## Failure Modes and Fallbacks

- Provider unavailable or no match found
- Backend model unavailable
- Chunk-level translation errors

Fallback behavior is partly implementation-dependent in callers; most flows prefer skip-with-report over hard crash.

## Quality Trade-offs

- Smaller chunks improve reliability but reduce cross-line context.
- Larger chunks improve fluency but raise timeout/error probability.
- Backend choice materially affects latency and output quality.
