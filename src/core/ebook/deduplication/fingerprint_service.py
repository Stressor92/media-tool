from __future__ import annotations

from pathlib import Path
import hashlib


class FingerprintService:
    """Create stable lightweight fingerprints for ebook files."""

    def fingerprint(self, file_path: Path) -> str:
        hasher = hashlib.sha256()
        with file_path.open("rb") as handle:
            first_chunk = handle.read(128 * 1024)
            hasher.update(first_chunk)
            handle.seek(0, 2)
            total_size = handle.tell()
            hasher.update(str(total_size).encode("ascii"))
        return hasher.hexdigest()
