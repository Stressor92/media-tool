# Ebook Module

## Responsibilities

The ebook domain provides a complete pipeline for **book identification, enrichment, normalization, organization, conversion, and duplicate analysis**.

It is one of the richest domains in the project and is organized as several cooperating subpackages rather than one monolithic service.

---

## Subsystems

| Subpackage | Responsibility |
|---|---|
| `identification/` | infer title/author/ISBN from files and metadata |
| `metadata/` | query external book metadata providers |
| `cover/` | fetch and embed cover art |
| `normalization/` | EPUB validation, metadata embedding, TOC generation |
| `organization/` | move/copy ebooks into library structure |
| `conversion/` | format conversion profiles and execution |
| `deduplication/` | group probable duplicates and select best versions |
| `workflow/` | compose the above into file-level and library-level operations |

---

## Core Models

The ebook layer is driven by explicit dataclasses in `models.py`.

| Model | Purpose |
|---|---|
| `BookIdentity` | identified title/author/ISBN plus confidence score |
| `BookMetadata` | enriched metadata returned by providers |
| `LibraryStructure` | target folder and filename derivation |
| `ProcessingResult` | end-to-end status for one ebook workflow |
| `ConversionProfile`, `ConversionResult` | conversion policy and output summary |
| `DuplicateGroup` | detected duplicate cluster metadata |

### Important scoring behavior

`BookIdentity.is_high_confidence()` currently treats `>= 0.8` as strong enough for automation, and `ConfidenceScorer.score_metadata_match(...)` weights:

- title similarity: **0.6**
- author similarity: **0.3**
- metadata completeness: **0.1**

---

## `EbookProcessor` Orchestration

`workflow/ebook_processor.py` is the main composition layer.

### `enrich(...)`

The enrich path performs:

1. identify the book from the file
2. optionally fetch provider metadata
3. optionally fetch a cover using the enriched metadata
4. optionally normalize the EPUB using metadata and cover
5. return a `ProcessingResult`

### `organize_library(...)`

The library-organize path:

1. scans for supported ebook extensions
2. identifies each file
3. optionally fetches metadata
4. builds a target path from `LibraryOrganizer`
5. moves or copies the file into the destination library

---

## Provider Pattern

The ebook layer uses explicit provider contracts.

### Metadata providers

`MetadataProvider` requires:

- `search_by_isbn()`
- `search_by_title()`
- `get_provider_name()`

### Cover providers

`CoverProvider` requires:

- `get_cover_by_isbn()`
- `search_covers()`
- `get_provider_name()`

This allows the orchestration layer to fan out across sources such as OpenLibrary and Google Books without binding the rest of the system to one backend.

---

## Normalization Pipeline

`EbookNormalizer.normalize()` performs mutation-heavy EPUB work in a guarded sequence:

1. validate the EPUB structure
2. create a backup (when enabled)
3. embed metadata
4. embed cover art
5. generate or repair the TOC
6. validate and either cleanup or rollback the backup
7. emit `EventType.EBOOK_PROCESSED` on success

This is one of the clearest examples of the project's **safe transformation** philosophy.

---

## Organization Strategy

Organization is delegated to `LibraryOrganizer`, which relies on `NamingService` and `FolderStructureBuilder`.

The output structure is based on metadata quality and aims to remain filesystem-safe and Jellyfin-friendly. When metadata is missing, the module falls back to degraded but still valid paths instead of failing outright.

---

## External Dependencies

- ebook metadata providers (OpenLibrary / Google Books integrations)
- cover image sources and Pillow-style image processing utilities
- EPUB read/write helpers in `src/utils`
- Calibre conversion support for some conversion flows

---

## Safety and Operational Characteristics

- dry-run support is available in orchestration layers
- backup/rollback protects destructive normalization operations
- provider outputs are ranked rather than blindly trusted
- organization can copy instead of move when required

Where a behavior depends on provider responses, fuzzy matching quality, or the richness of the source file, it should be treated as **implementation-dependent**.
