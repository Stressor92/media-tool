# Internal: Provider Pattern

## Scope

Several parts of the project interact with external or replaceable backends. Rather than hard-coding every integration, the repository uses a **provider/protocol pattern** that separates orchestration from implementation.

---

## Why this pattern exists

The codebase needs to support variability in areas such as:

- subtitle sources
- translation backends
- ebook metadata sources
- ebook cover sources
- runner abstractions in some download/testing paths

If those dependencies were referenced directly everywhere, testing and replacement would become fragile.

---

## Main Contracts

| Contract | Location | Used by |
|---|---|---|
| `SubtitleProvider` | `core/subtitles/subtitle_provider.py` | `SubtitleDownloadManager` |
| `TranslatorProtocol` | `core/translation/translator_protocol.py` | `SubtitleTranslator` / `translator_factory` |
| `MetadataProvider` | `core/ebook/metadata/providers/provider.py` | `MetadataService` |
| `CoverProvider` | `core/ebook/cover/providers/provider.py` | `CoverService` |
| `YtDlpRunnerProtocol` | `core/download/yt_dlp_runner.py` | `DownloadManager` |

---

## Common Shape

Most provider contracts follow the same architectural pattern:

1. define a small abstract interface or protocol
2. keep orchestration in a service class
3. choose one or more concrete implementations elsewhere
4. return typed domain objects rather than raw HTTP/subprocess payloads

This is visible in the subtitle and ebook subsystems especially clearly.

---

## Benefits

### Swapability

A new backend can be introduced without rewriting the orchestration layer.

### Testability

Service classes can be tested with fakes or mocks that satisfy the provider contract.

### Boundary clarity

External volatility is isolated at the edge of the system instead of leaking into all call sites.

---

## Trade-offs

The provider pattern is not free:

- it adds extra indirection during debugging
- the common contract may be narrower than the richest backend’s capabilities
- capability mismatches can force some lowest-common-denominator behavior

Even so, for this codebase the pattern is a good fit because external services and local ML backends are expected to evolve independently of the core orchestration logic.