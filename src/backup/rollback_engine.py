from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

from .models import BackupEntry, CorruptBackupError, RollbackError


class RollbackEngine:
    def restore(self, entry: BackupEntry) -> None:
        backup_path = Path(entry.backup_path)
        original_path = Path(entry.original_path)
        output_path = Path(entry.output_path) if entry.output_path else None

        if not backup_path.exists():
            raise RollbackError(f"Backup file is missing: {backup_path}")

        backup_hash = self._sha256(backup_path)
        if backup_hash != entry.original_hash:
            raise CorruptBackupError("Backup hash mismatch; rollback aborted")

        if output_path is not None and output_path.exists() and output_path != original_path:
            output_path.unlink(missing_ok=True)

        original_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(backup_path, original_path)

        restored_hash = self._sha256(original_path)
        if restored_hash != entry.original_hash:
            raise RollbackError("Restored file hash mismatch")

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            while True:
                chunk = handle.read(1024 * 1024)
                if not chunk:
                    break
                digest.update(chunk)
        return f"sha256:{digest.hexdigest()}"
