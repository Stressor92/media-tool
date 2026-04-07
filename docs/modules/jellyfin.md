# Jellyfin Module

## Responsibilities

The Jellyfin domain provides **server-side library inspection and repair** for already-ingested media. It complements the local file-processing pipeline by working against the Jellyfin REST API rather than the raw filesystem.

---

## Core Components

| File | Role |
|---|---|
| `client.py` | thin HTTP client with retries and structured exceptions |
| `library_manager.py` | library refresh, scan-status checks, and item retrieval |
| `metadata_inspector.py` | identify missing or suspicious metadata on server items |
| `metadata_fixer.py` | attempt safe automated repairs for fixable issue categories |
| `auto_trigger.py` | bridge from local workflows to server refresh triggers |
| `models.py` | typed issue and result models |

---

## HTTP Client Design

`JellyfinClient` is intentionally small but opinionated:

- uses a lazily created `requests.Session`
- configures retry behavior for `500`, `502`, `503`, and `504`
- attaches a MediaBrowser-compatible authorization header
- maps status codes into domain-specific exceptions such as:
  - `JellyfinAuthError`
  - `JellyfinNotFoundError`
  - `JellyfinServerError`

This prevents the rest of the module from having to reason about raw HTTP status codes.

---

## Inspection Model

The server-side inspector focuses on metadata quality problems such as:

- missing overview/year/poster/backdrop
- unmatched provider ids
- missing episode numbering or wrong series assignment
- duplicate or otherwise suspicious items

Most checks are deterministic against the JSON returned by Jellyfin. Some path-derived heuristics remain implementation-dependent.

---

## Fix Strategy

The fixer intentionally draws a boundary between:

- **safe, refresh-based automation** for recoverable issues, and
- **manual or guided intervention** where ambiguity is high

This is consistent with the project's broader safety model: when the system is not confident, it prefers to surface the issue instead of silently mutating it.

---

## Integration Points

The Jellyfin module can be used:

- directly through the `jellyfin` CLI command group
- after local media organization to trigger refreshes or validation
- alongside audit and metadata workflows when validating library quality end-to-end

It depends on correct configuration for:

- `jellyfin.base_url`
- `jellyfin.api_key`
- optional scan wait/timeout behavior

---

## Operational Constraints

Because this module depends on a live Jellyfin server, its behavior is sensitive to:

- server availability
- API permissions
- network latency and retry conditions
- library layout consistency inside Jellyfin

Those environmental factors are external to the local media-processing code and should be treated separately from source-level defects.
