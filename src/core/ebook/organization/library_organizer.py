from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from core.ebook.models import BookMetadata
from core.ebook.organization.folder_structure import FolderStructureBuilder
from core.ebook.organization.naming_service import NamingService
from utils.file_operations import FileOperationError, FileOperations

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class OrganizationResult:
    """Result of one library organization operation."""

    success: bool
    original_path: Path
    new_path: Path | None = None
    action: str = "unknown"  # moved | copied | skipped | dry_run
    error_message: str | None = None


class LibraryOrganizer:
    """Organize ebook files into Jellyfin-compatible library structure."""

    def __init__(self, naming_service: NamingService, dry_run: bool = False) -> None:
        self.naming = naming_service
        self.structure_builder = FolderStructureBuilder(naming_service)
        self.dry_run = dry_run

    def organize(
        self,
        ebook_path: Path,
        metadata: BookMetadata,
        library_root: Path,
        copy_instead_of_move: bool = False,
        overwrite: bool = False,
    ) -> OrganizationResult:
        if not ebook_path.exists() or not ebook_path.is_file():
            return OrganizationResult(
                success=False,
                original_path=ebook_path,
                error_message=f"Input file does not exist: {ebook_path}",
            )

        structure = self.structure_builder.build(metadata, library_root)
        target_folder = structure.folder_path
        target_filename = f"{structure.filename}{ebook_path.suffix.lower()}"
        target_path = target_folder / target_filename

        if target_path.exists() and not overwrite:
            if target_path.resolve() == ebook_path.resolve():
                return OrganizationResult(
                    success=True,
                    original_path=ebook_path,
                    new_path=target_path,
                    action="skipped",
                )
            return OrganizationResult(
                success=False,
                original_path=ebook_path,
                new_path=target_path,
                error_message="Target file already exists",
            )

        if self.dry_run:
            return OrganizationResult(
                success=True,
                original_path=ebook_path,
                new_path=target_path,
                action="dry_run",
            )

        try:
            if copy_instead_of_move:
                FileOperations.copy(ebook_path, target_path, overwrite=overwrite, dry_run=False)
                action = "copied"
            else:
                FileOperations.move(ebook_path, target_path, overwrite=overwrite, dry_run=False)
                action = "moved"

            logger.info(
                "Ebook organized",
                extra={"source": str(ebook_path), "target": str(target_path), "action": action},
            )
            return OrganizationResult(
                success=True,
                original_path=ebook_path,
                new_path=target_path,
                action=action,
            )
        except FileOperationError as exc:
            logger.error("Organization failed", extra={"error": str(exc), "path": str(ebook_path)})
            return OrganizationResult(
                success=False,
                original_path=ebook_path,
                new_path=target_path,
                error_message=str(exc),
            )

    def batch_organize(
        self,
        ebooks: list[tuple[Path, BookMetadata]],
        library_root: Path,
        copy_instead_of_move: bool = False,
        overwrite: bool = False,
    ) -> list[OrganizationResult]:
        results: list[OrganizationResult] = []
        for ebook_path, metadata in ebooks:
            results.append(
                self.organize(
                    ebook_path,
                    metadata,
                    library_root,
                    copy_instead_of_move=copy_instead_of_move,
                    overwrite=overwrite,
                )
            )
        return results
