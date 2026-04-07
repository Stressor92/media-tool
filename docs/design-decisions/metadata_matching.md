# Design Decision: Metadata Matching

## Problem

The system frequently needs to infer metadata from imperfect inputs:

- noisy movie filenames containing release tags
- ebooks with missing or incomplete embedded metadata
- partial title/author information
- inconsistent year information

A strict exact-match strategy would miss too many valid items, while a naive fuzzy strategy would risk wrong matches.

---

## Options Considered

### Option A — exact match only

**Pros**
- very low false-positive rate

**Cons**
- too many misses on real-world filenames and legacy files

### Option B — fully manual selection everywhere

**Pros**
- high operator control

**Cons**
- poor batch scalability
- not suitable for unattended workflows

### Option C — heuristic-first matching with optional operator override (**chosen**)

**Pros**
- scalable for batch runs
- still allows manual intervention when ambiguity is high

**Cons**
- relies on heuristic quality and provider ordering

---

## Chosen Solution

The repository uses **domain-specific matching strategies** rather than one universal matcher.

### Movie metadata path

For video metadata in `core/metadata`:

1. `title_parser.py` strips quality/release tags and extracts an optional year
2. `TmdbProvider.search(...)` returns ranked candidates from TMDB
3. `MatchSelector` either:
   - selects the first result in `AUTO` mode, or
   - prompts the user in `INTERACTIVE` mode

This means movie auto-selection currently leans on **provider ranking plus local title cleanup**, not a heavy custom scoring engine.

### Ebook metadata path

For ebooks in `core/ebook`:

1. ISBN lookup is attempted first when available
2. provider results are collected by title/author when necessary
3. candidates are ranked using `ConfidenceScorer.score_metadata_match(...)`

The scoring weights are currently:

- title similarity: `0.6`
- author similarity: `0.3`
- metadata completeness: `0.1`

This is more explicit than the movie path because ebook metadata often arrives from weaker or more heterogeneous signals.

---

## Trade-offs

| Strategy | Benefit | Cost |
|---|---|---|
| regex-based title cleanup | robust against common release-name noise | can still fail on very unusual naming |
| TMDB-first ordering for movies | simple and fast | quality depends heavily on provider ranking |
| ISBN-first lookup for ebooks | strong precision when ISBN exists | many files lack ISBN data |
| fuzzy + completeness scoring for ebooks | better batch automation on incomplete data | still heuristic, not guaranteed |

---

## Future Considerations

If matching accuracy becomes a larger concern, the most natural evolution would be to make movie matching more explicit and scored in the same way ebook matching already is. Until then, the documented behavior should be treated as **heuristic automation with optional human override**, not as a guaranteed identity resolver.