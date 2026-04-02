from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class FileOperationPlan:
    """Describes one planned move/copy operation without executing it."""

    source: Path
    destination: Path
    operation: str  # move | copy


class FileOperationError(RuntimeError):
    """Raised when file operation preconditions fail."""


class FileOperations:
    """Safe file operations with optional dry-run semantics."""

    @staticmethod
    def validate_source(source: Path) -> None:
        if not source.exists():
            raise FileOperationError(f"Source does not exist: {source}")
        if not source.is_file():
            raise FileOperationError(f"Source is not a file: {source}")

    @staticmethod
    def validate_destination(destination: Path, overwrite: bool = False) -> None:
        if destination.exists() and not overwrite:
            raise FileOperationError(f"Destination already exists: {destination}")

    @staticmethod
    def ensure_parent(destination: Path, dry_run: bool = False) -> None:
        if dry_run:
            return
        destination.parent.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def create_backup(file_path: Path, suffix: str = ".bak", dry_run: bool = False) -> Path:
        backup_path = file_path.with_suffix(file_path.suffix + suffix)
        if dry_run:
            return backup_path
        shutil.copy2(file_path, backup_path)
        return backup_path

    @classmethod
    def move(
        cls,
        source: Path,
        destination: Path,
        *,
        overwrite: bool = False,
        dry_run: bool = False,
    ) -> FileOperationPlan:
        cls.validate_source(source)
        cls.validate_destination(destination, overwrite=overwrite)
        cls.ensure_parent(destination, dry_run=dry_run)
        if not dry_run:
            shutil.move(str(source), str(destination))
        return FileOperationPlan(source=source, destination=destination, operation="move")

    @classmethod
    def copy(
        cls,
        source: Path,
        destination: Path,
        *,
        overwrite: bool = False,
        dry_run: bool = False,
    ) -> FileOperationPlan:
        cls.validate_source(source)
        cls.validate_destination(destination, overwrite=overwrite)
        cls.ensure_parent(destination, dry_run=dry_run)
        if not dry_run:
            shutil.copy2(source, destination)
        return FileOperationPlan(source=source, destination=destination, operation="copy")
