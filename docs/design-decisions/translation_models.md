# Design Decision: Subtitle Translation Model

## Problem

Subtitle translation is not just plain text translation. The system must preserve:

- timing boundaries
- multi-line structure
- inline tags (HTML/ASS markup)
- style and positional information for richer formats

At the same time, translating one line completely independently often loses sentence context.

---

## Options Considered

### Option A — translate each subtitle segment independently

**Pros**
- trivial to implement
- easy mapping back to original timing

**Cons**
- poor context for pronouns and sentence flow
- awkward grammar across line boundaries

### Option B — translate the raw file as one large string

**Pros**
- maximal context

**Cons**
- very hard to preserve segment alignment and formatting
- risky for large files and mixed-format markup

### Option C — translate a format-independent intermediate model in chunks (**chosen**)

**Pros**
- preserves segment/timing structure
- provides enough context for better translation quality
- supports multiple subtitle formats through one internal representation

**Cons**
- more orchestration complexity
- chunk splitting/restoration can still be imperfect in edge cases

---

## Chosen Solution

The current implementation uses:

- `SubtitleDocument` and `SubtitleSegment` as the internal representation
- `LanguagePair` for explicit source/target language intent
- `build_chunks()` to group neighboring segments (`max_segments=4`, `max_chars=250` by default)
- tag extraction/restoration via `TagProcessor`
- backend indirection through `TranslatorProtocol` and `create_translator()`

### Why an intermediate model?

Because the code supports multiple formats (`srt`, `ass`, `ssa`, `vtt`, `ttml`, `lrc`, etc.), a single internal model is easier to reason about than implementing format-specific translation logic in every parser/writer pair.

### Why chunking?

Chunking provides a compromise between:

- **local alignment** needed for timing preservation, and
- **enough context** for better translation quality

When the translated line count does not match the original chunk structure, the code falls back to proportional redistribution rather than failing outright.

---

## Backend Choice

The factory currently supports:

- `opus-mt` as the default path
- `argos` as a fallback/backend alternative

This keeps the orchestration layer independent of any specific translation engine while still exposing a stable developer-facing contract.

---

## Trade-offs

| Decision | Benefit | Cost |
|---|---|---|
| intermediate subtitle model | multi-format support and cleaner orchestration | more code than direct line translation |
| placeholder-based tag preservation | reduced formatting corruption | placeholder handling adds complexity |
| chunk-based translation | better grammar/context | occasional imperfect re-splitting |
| backend abstraction | easy backend swapping | capability differences between backends |

---

## Future Considerations

Possible future work includes better automatic source-language inference and more advanced quality heuristics, but those should remain clearly separated from the current guarantees: **timing preservation, formatting safety, and deterministic output writing**.