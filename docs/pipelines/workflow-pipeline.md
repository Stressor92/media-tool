# Workflow Pipeline

## Objective

Describe the end-to-end staged pipeline executed by the workflow runner for library-wide movie/series processing.

## Stage Sequence

1. Pre-scan and candidate grouping (implementation-dependent at caller layer)
2. Merge language duplicates (`s01_merge_language_dupes`)
3. Remux mp4 to mkv (`s02_mp4_to_mkv`)
4. Upscale DVD-like inputs (`s03_upscale_dvd`)
5. Re-encode Blu-ray/high-quality profiles (`s04_encode_bluray`)
6. Subtitle acquisition/translation (`s05_subtitles`)
7. Final organization (`s06_organize`)

Each stage can skip items when preconditions fail.

## Data Flow

- Input file set enters shared workflow context.
- Stage outputs update context references and per-step status.
- Later stages consume transformed paths from earlier stages.

This path mutation model avoids re-discovering files between stages.

## Safety and Validation

- Mutating stages may use backup checkpoints.
- Post-checks verify expected output existence/health.
- Failures are captured per stage for diagnostics.

## Typical Branching

- Non-mp4 inputs bypass remux stage.
- Non-DVD candidates bypass upscale stage.
- Subtitle stage may skip when subtitles already exist or providers fail.

## Operational Trade-offs

- Sequential deterministic ordering simplifies reproducibility.
- Throughput is lower than aggressive parallel fan-out but side-effect control is stronger.
