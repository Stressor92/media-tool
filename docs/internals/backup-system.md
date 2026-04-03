# Internals: Backup System

## Architecture

The backup subsystem is centered on `BackupManager`, with supporting components:

- `backup_index`: lifecycle state tracking
- validators: integrity checks before cleanup
- `rollback_engine`: restoration mechanics
- `storage_guard`: capacity and retention safety controls

## Lifecycle

1. Create backup entry before risky mutation.
2. Execute operation.
3. Validate resulting output against backup entry.
4. If valid, cleanup backup artifacts.
5. If invalid or failed, rollback from backup.

## Data Model

Entries include status and metadata sufficient for:

- rollback addressability
- media type and operation attribution
- audit/debug visibility

## Decorator Integration

`with_backup` provides an operation wrapper that attempts to infer input/output paths and automate create/validate/cleanup.

This is a convenience path; explicit backup orchestration remains available for complex flows.

## Failure Semantics

Backup failures are often logged as warnings and operations may still proceed, depending on caller policy. This balances availability and safety in environments with constrained disk or permissions.
