# Design Decision: Naming Strategy

## Problem

A media-processing tool that targets Jellyfin/NAS libraries must create paths and filenames that are:

- predictable across runs
- safe for Windows filesystems
- understandable to media servers
- derived from imperfect metadata without becoming brittle

If every command constructs names ad hoc, library layout quickly becomes inconsistent.

---

## Options Considered

### Option A — preserve incoming filenames everywhere

**Pros**
- trivial implementation
- preserves original naming exactly

**Cons**
- source names are often noisy or inconsistent
- poor server indexing and ugly library presentation

### Option B — custom naming logic embedded in each workflow

**Pros**
- local flexibility

**Cons**
- duplicated rules
- inconsistent evolution over time
- hard to test centrally

### Option C — central naming helpers and structure builders (**chosen**)

**Pros**
- one place to evolve naming rules
- more consistent library layout
- safer sanitation and fallback behavior

**Cons**
- requires shared conventions across modules

---

## Chosen Solution

The repository centralizes naming in helpers such as:

- `utils.jellyfin_naming.JellyfinNaming`
- ebook `NamingService` and `FolderStructureBuilder`
- workflow step `s06_organize.py` for the final movie placement pattern

### Movie layout

The current workflow organization step derives output as:

```text
<output_dir>/<stem>/<stem><suffix>
```

This keeps folder and primary file names aligned and easy for Jellyfin to scan.

### Ebook layout

The ebook organization system is richer and can use author/series/title-aware structures through `LibraryStructure` and `LibraryOrganizer`.

---

## Safety Aspects

Naming helpers also sanitize invalid filesystem characters and normalize whitespace, which is especially important on Windows targets.

This allows the system to keep producing valid paths even when upstream metadata is incomplete or contains problematic punctuation.

---

## Trade-offs

| Decision | Benefit | Cost |
|---|---|---|
| centralized naming helpers | consistent library layout | shared conventions must be maintained carefully |
| fallback-friendly path generation | fewer hard failures during automation | some outputs may still need later manual cleanup |
| Jellyfin-oriented conventions | better media-server compatibility | not every external naming preference is preserved |

---

## Future Considerations

Future extensions can add more templates or richer series/movie distinctions, but the current architectural direction should remain the same: **naming policy belongs in shared services, not scattered through CLI commands or one-off scripts**.