# Workflow Module

## Purpose

The workflow subsystem provides a **deterministic orchestration layer** for multi-step library automation. It does not re-implement video or subtitle logic; instead, it composes those domain services into a fixed execution plan.

The current default orchestration is the **movie pipeline** exposed by `workflow movies`.

---

## Core Building Blocks

| File | Responsibility |
|---|---|
| `models.py` | `WorkflowContext`, `StepResult`, `StepStatus`, `WorkflowResult` |
| `step.py` | abstract `BaseStep` lifecycle contract |
| `runner.py` | sequential execution and `build_movie_pipeline()` |
| `steps/s01_*.py` ... `steps/s06_*.py` | concrete media-processing stages |

---

## Step Contract

Every workflow step inherits from `BaseStep` and follows the same lifecycle:

1. `precondition(ctx)` — decide if the step should run
2. `run(ctx)` — perform the operation and return a `StepResult`
3. `post_check(ctx, result)` — verify output correctness after a successful run

The shared `execute()` method handles:

- logging around each phase
- exception-to-`FAILED` conversion
- adding the result to `ctx.completed_steps`
- optional post-check failure escalation

This gives the runner a uniform interface even though the concrete steps perform very different kinds of work.

---

## Shared State Model

`WorkflowContext` is the transport object passed through the pipeline.

### Important fields

| Field | Purpose |
|---|---|
| `source_dir` | input root for the run |
| `output_dir` | final target library root |
| `dry_run` | preview mode without mutations |
| `stop_on_failure` | abort on first failed step vs continue |
| `working_files` | current in-flight file set after each step |
| `metadata` | transient step-to-step scratch space |
| `completed_steps` | ordered execution history |

The key design choice is that **later steps consume the file list produced by earlier steps**, avoiding re-discovery of transformed outputs.

---

## Current Movie Pipeline

`build_movie_pipeline()` currently wires the following six steps in order:

| Step | File | Responsibility |
|---|---|---|
| `01_merge_language_dupes` | `s01_merge_language_dupes.py` | combine same-title language variants into a merged MKV |
| `02_mp4_to_mkv` | `s02_mp4_to_mkv.py` | lossless remux remaining MP4 files |
| `03_upscale_dvd` | `s03_upscale_dvd.py` | upscale low-resolution or DVD-like sources |
| `04_encode_bluray` | `s04_encode_bluray.py` | HEVC re-encode high-bitrate Blu-ray/remux inputs |
| `05_subtitles` | `s05_subtitles.py` | acquire subtitles through OpenSubtitles; Whisper fallback is noted as TODO |
| `06_organize` | `s06_organize.py` | move results into Jellyfin-style output folders |

> The pipeline currently does **not** include metadata enrichment as a workflow step. Metadata runs remain a separate `metadata` module/CLI concern.

---

## Failure and Skip Semantics

The workflow distinguishes several states:

- `SUCCESS` — operation completed normally
- `SKIPPED` — precondition not met or step intentionally bypassed
- `FAILED` — step errored or post-check failed
- `PARTIAL` — some work completed but not all candidates succeeded

`WorkflowRunner.run()` stops immediately on `FAILED` when `ctx.stop_on_failure` is `True`. The CLI exposes the inverse behavior via `--keep-going`.

This makes the engine suitable for both:

- strict automation runs, and
- exploratory or salvage-oriented batch runs

---

## Why the workflow is sequential

The orchestration intentionally favors **predictability over maximal throughput**.

Reasons:

- later steps depend on exact outputs of earlier steps
- destructive mutations are easier to validate and roll back in order
- per-step logs and reports are easier to interpret
- file naming and movement stay deterministic

Parallelism is therefore pushed down into read-heavy helpers, not the top-level step runner.

---

## Integration Points

The workflow module depends on but does not own:

- video transforms (`core.video.*`)
- subtitle acquisition (`core.subtitles.*`)
- output organization and naming helpers
- backup safety and statistics emitted by underlying services

As a result, the workflow layer remains a relatively small orchestration shell around richer domain modules.

---

## Extending the Workflow

To add a new stage safely:

1. create a new `BaseStep` subclass
2. keep preconditions cheap and deterministic
3. return a `StepResult` instead of printing or raising for operational failures
4. update `build_movie_pipeline()` order intentionally
5. prefer reading/writing `ctx.metadata` for transient coordination, not global state

That extension model is one of the cleanest architectural seams in the project.
