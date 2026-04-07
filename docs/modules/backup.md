# Backup Module

## Purpose

The backup subsystem provides **transaction-like safety** for destructive or mutation-heavy operations. Its goal is simple: if a transformation produces a bad output, the original file should still be recoverable.

---

## Core Components

| File | Role |
|---|---|
| `backup_manager.py` | high-level orchestration for create, validate, cleanup, rollback |
| `backup_index.py` | persistent index of backup entries |
| `models.py` | `BackupEntry`, `BackupStatus`, `ValidationResult`, `RetentionPolicy` |
| `rollback_engine.py` | restoration mechanics |
| `storage_guard.py` | quota checks and storage protection |
| `validators/*` | media-type-specific output validation |

---

## Lifecycle

A typical backup-enabled operation follows this sequence:

```text
create backup -> run transformation -> validate output -> cleanup backup
                                             \-> rollback on failure
```

### `create(...)`

`BackupManager.create()`:

- verifies that the original path exists
- checks quota via `StorageGuard`
- copies the original file into the configured backup directory
- computes and stores a SHA-256 hash
- persists a `BackupEntry` with status `PENDING`
- emits a backup-created statistics event

### `validate(...)`

Validation is delegated by media type:

- `VideoValidator`
- `AudioValidator`
- `EbookValidator`
- `AudiobookValidator`

The output is recorded as a `ValidationResult`, and the entry transitions to `VALIDATED` or `FAILED`.

### `cleanup(...)`

If validation passed and retention policy allows cleanup, the backup file is removed and the entry becomes `CLEANED`.

### `rollback(...)`

If a transformation fails or validation does not pass, `RollbackEngine.restore(entry)` is invoked and the entry is marked `ROLLED_BACK`.

---

## Data Model

### `BackupEntry`

A backup record stores:

- unique id
- operation name
- media type
- original path and backup path
- original hash
- size and timestamps
- validation result
- status and retention information

### `BackupStatus`

Important states include:

- `PENDING`
- `VALIDATED`
- `FAILED`
- `ROLLED_BACK`
- `CLEANED`
- `EXPIRED`
- `KEPT`

This explicit state machine makes inspection and troubleshooting much easier than relying on ad hoc temp-file behavior.

---

## Configuration and Retention

The backup system is driven by `config.backup` values such as:

- `backup_dir`
- `max_size_gb`
- `auto_cleanup.after_days`
- validation tolerances for video/audio/audiobook/ebook checks

Retention policy can result in immediate cleanup, delayed cleanup, or explicit keep behavior depending on the configured settings.

---

## Integration Pattern

The backup layer is used directly by operations such as:

- video remuxing
- video merging
- DVD upscaling
- ebook normalization

The public shim `src.backup` also exposes helpers like `get_backup_manager()` and the `with_backup(...)` decorator for convenience.

---

## Design Trade-off

The subsystem adds disk I/O and validation overhead, but it significantly reduces the risk of irreversible damage during large automated batch runs. In a NAS/Jellyfin pipeline, that trade-off is usually worth the extra safety.
