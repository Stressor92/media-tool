from __future__ import annotations

import logging
from pathlib import Path
import shutil
import subprocess

logger = logging.getLogger(__name__)


class CalibreNotFoundError(RuntimeError):
    """Calibre executable was not found in PATH."""


class CalibreConversionError(RuntimeError):
    """Calibre conversion command failed."""


class CalibreRunner:
    """Wrapper around the Calibre CLI tools ebook-convert and ebook-meta."""

    def __init__(self, calibre_binary: str = "ebook-convert", meta_binary: str = "ebook-meta") -> None:
        self.calibre_binary = calibre_binary
        self.meta_binary = meta_binary
        self._verify_installation()

    def _verify_installation(self) -> None:
        if shutil.which(self.calibre_binary) is None:
            raise CalibreNotFoundError(
                f"Calibre tool '{self.calibre_binary}' not found. Install from https://calibre-ebook.com/download"
            )

    def convert(
        self,
        input_path: Path,
        output_path: Path,
        extra_args: list[str] | None = None,
        timeout: int = 600,
    ) -> subprocess.CompletedProcess[bytes]:
        if not input_path.exists() or not input_path.is_file():
            raise CalibreConversionError(f"Input file does not exist: {input_path}")

        cmd = [self.calibre_binary, str(input_path), str(output_path)]
        if extra_args:
            cmd.extend(extra_args)

        try:
            logger.info("Converting ebook", extra={"input": str(input_path), "output": str(output_path)})
            return subprocess.run(cmd, capture_output=True, check=True, timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            raise CalibreConversionError(f"Conversion timed out after {timeout} seconds") from exc
        except subprocess.CalledProcessError as exc:
            stderr = (exc.stderr or b"").decode("utf-8", errors="replace")
            raise CalibreConversionError(f"Conversion failed: {stderr.strip()}") from exc

    def get_metadata(self, ebook_path: Path, timeout: int = 30) -> dict[str, str]:
        if shutil.which(self.meta_binary) is None:
            return {}

        try:
            result = subprocess.run(
                [self.meta_binary, str(ebook_path)],
                capture_output=True,
                check=True,
                timeout=timeout,
            )
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
            return {}

        output = result.stdout.decode("utf-8", errors="replace")
        metadata: dict[str, str] = {}
        for line in output.splitlines():
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            metadata[key.strip().lower()] = value.strip()
        return metadata
