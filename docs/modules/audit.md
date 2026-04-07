# Audit Module

## Purpose

The audit domain performs **library-quality analysis** over local media collections. It is designed to answer the question: *“What is wrong or suspicious in this library before I mutate or organize it?”*

---

## Core Components

| File | Role |
|---|---|
| `auditor.py` | top-level orchestration over discovered files |
| `check_registry.py` | register and filter the active check set |
| `check.py` | base check contract |
| `checks/*` | concrete checks grouped by category |
| `models.py` | findings, severities, report objects |
| `reporter.py` | CLI-/export-oriented report rendering |

---

## Execution Model

`LibraryAuditor.audit(root_dir, recursive=True)` performs the following:

1. validate the root path
2. discover media files by extension
3. pre-probe them through `FfprobeCache`
4. resolve the active check set from `CheckRegistry`
5. execute each check against the same file/probe dataset
6. aggregate the results into an `AuditReport`

This design avoids repeatedly probing the same files for every check.

---

## Check Categories

The default registry combines checks from several domains:

- **subtitle checks** (`MissingDeSubtitleCheck`, `MissingEnSubtitleCheck`, `NoSubtitlesAtAllCheck`)
- **audio checks** (`UnlabeledAudioCheck`, `MissingDeAudioCheck`)
- **series checks** (`EpisodeGapCheck`, `BadEpisodeNamingCheck`)
- **technical file checks** (`BrokenFileCheck`, `WrongContainerCheck`, `InefficientCodecCheck`, `LowBitrateCheck`, `SuspiciousFileSizeCheck`)
- **naming/layout checks** (`BadMovieNamingCheck`, `DuplicateMovieCheck`, `SpecialCharsCheck`, `NameTooLongCheck`)
- **root-aware checks** (`FileInRootCheck`, `EmptyFolderCheck`)

This makes the audit layer an extensible quality gate rather than a single hard-coded report.

---

## Why the registry matters

`CheckRegistry` decouples:

- the **set of available checks**, and
- the **orchestration logic** that runs them

That means new rules can be added without changing `LibraryAuditor` itself, as long as the new check conforms to the base contract.

---

## Findings and Severity Model

The report layer is strongly typed so the same audit output can serve:

- human-readable CLI summaries
- export/report generation
- preflight quality gates before conversion or organization

This consistency is important for large batch libraries where the same findings need to be triaged repeatedly.

---

## Integration Points

The audit module is often used:

- before organization to identify naming/layout problems
- before destructive conversion to surface bad sources
- alongside Jellyfin inspection for a fuller “filesystem + server metadata” picture

It is intentionally read-oriented and should be safe to run repeatedly against large collections.
