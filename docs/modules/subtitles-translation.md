# Subtitles and Translation Modules

## Scope

These modules handle subtitle acquisition and language translation with provider abstraction and backend-specific translation engines.

## Main Components

Subtitles:

- `subtitle_downloader`: orchestration for search/download decisions
- `opensubtitles_provider`: concrete remote provider implementation
- `subtitle_provider`: provider protocol/interface

Translation:

- `subtitle_translator`: translation orchestration over subtitle segments
- `translator_factory`: backend resolver and construction
- `translator_protocol`: shared translator contract
- `chunking`: segmentation strategy for model/token constraints

## Provider and Backend Abstraction

Both areas use interface contracts:

- Subtitle acquisition can swap provider implementation
- Translation backend can switch (for example Opus-MT or Argos)

This isolates orchestration from vendor/backend specifics.

## Subtitle Acquisition Behavior

Acquisition uses best-effort search/match logic with network retries and provider-specific error handling.

Important behavior:

- Can return no subtitle without hard process crash
- Caller decides fallback, retry, or skip policy

## Translation Flow

Translation path generally:

1. Parse subtitle content into units.
2. Chunk units to backend-safe sizes.
3. Translate chunk text while preserving timing structure.
4. Reconstruct translated subtitles.

Chunking and tag-preservation logic are critical to keep subtitle structure valid.

## Trade-offs

- Backend abstraction improves portability.
- Translation quality/speed depends strongly on selected backend and language pair.
- Chunk boundaries can affect fluency; larger chunks improve context but increase failure risk/time.

## Integration Points

- Workflow subtitle step consumes downloader and translation path.
- Configuration controls provider/backend choice and related tuning.
- Failures are typically surfaced as step-level warnings/errors in workflow outputs.
