"""MP3 loudness normalization via mp3gain without re-encoding."""

from __future__ import annotations

import logging
import os
from collections import defaultdict
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path

from utils.mp3gain_runner import MP3GainResult, run_mp3gain

logger = logging.getLogger(__name__)

MP3GainRunner = Callable[[list[str]], MP3GainResult]


class MP3GainStatus(Enum):
    """Result status for MP3Gain normalization operations."""

    UPDATED = auto()
    SKIPPED = auto()
    FAILED = auto()


@dataclass(frozen=True)
class MP3GainFileResult:
    """Outcome for a single MP3 loudness normalization attempt."""

    path: Path
    status: MP3GainStatus
    error: str | None = None


class MP3GainNormalizer:
    """Normalize MP3 loudness using mp3gain in track or album mode."""

    def __init__(self, runner: MP3GainRunner | None = None, max_command_chars: int = 7000) -> None:
        self._runner = runner or run_mp3gain
        self._max_command_chars = max(1000, max_command_chars)

    def normalize_path(
        self,
        path: Path,
        recursive: bool = True,
        album_mode: bool = False,
        target_db: float = 89.0,
        prevent_clipping: bool = True,
    ) -> list[MP3GainFileResult]:
        """Normalize one MP3 file or all MP3 files in a directory."""
        if not path.exists():
            return [
                MP3GainFileResult(
                    path=path,
                    status=MP3GainStatus.FAILED,
                    error="Datei oder Verzeichnis nicht gefunden.",
                )
            ]

        if path.is_file():
            return self._normalize_file_batch(
                [path],
                album_mode=album_mode,
                target_db=target_db,
                prevent_clipping=prevent_clipping,
            )

        if not path.is_dir():
            return [MP3GainFileResult(path=path, status=MP3GainStatus.FAILED, error="Ungueltiger Pfadtyp.")]

        iterator = path.rglob("*") if recursive else path.glob("*")
        files = sorted((entry for entry in iterator if entry.is_file()), key=lambda entry: str(entry).lower())
        if not files:
            return []

        return self._normalize_directory_files(
            files,
            album_mode=album_mode,
            target_db=target_db,
            prevent_clipping=prevent_clipping,
        )

    def _normalize_directory_files(
        self,
        files: list[Path],
        album_mode: bool,
        target_db: float,
        prevent_clipping: bool,
    ) -> list[MP3GainFileResult]:
        if not album_mode:
            return self._normalize_file_batch(
                files,
                album_mode=False,
                target_db=target_db,
                prevent_clipping=prevent_clipping,
            )

        grouped: dict[Path, list[Path]] = defaultdict(list)
        for file_path in files:
            grouped[file_path.parent].append(file_path)

        results: list[MP3GainFileResult] = []
        for album_dir in sorted(grouped.keys(), key=lambda candidate: str(candidate).lower()):
            results.extend(
                self._normalize_file_batch(
                    grouped[album_dir],
                    album_mode=True,
                    target_db=target_db,
                    prevent_clipping=prevent_clipping,
                )
            )
        return results

    def _normalize_file_batch(
        self,
        files: Iterable[Path],
        album_mode: bool,
        target_db: float,
        prevent_clipping: bool,
    ) -> list[MP3GainFileResult]:
        mp3_files: list[Path] = []
        results: list[MP3GainFileResult] = []

        for file_path in files:
            if not file_path.exists() or not file_path.is_file():
                results.append(
                    MP3GainFileResult(path=file_path, status=MP3GainStatus.FAILED, error="Datei nicht gefunden.")
                )
                continue
            if file_path.suffix.lower() != ".mp3":
                results.append(
                    MP3GainFileResult(path=file_path, status=MP3GainStatus.SKIPPED, error="Nur MP3 wird unterstuetzt.")
                )
                continue
            if not self._supports_mp3gain_path(file_path):
                results.append(
                    MP3GainFileResult(
                        path=file_path,
                        status=MP3GainStatus.FAILED,
                        error="Dateiname/Pfad enthaelt Zeichen, die MP3Gain auf Windows nicht lesen kann.",
                    )
                )
                continue
            mp3_files.append(file_path)

        if not mp3_files:
            return results

        base_args = self._build_base_args(
            album_mode=album_mode,
            target_db=target_db,
            prevent_clipping=prevent_clipping,
        )
        for chunk in self._chunk_files(mp3_files, base_args):
            results.extend(self._apply_chunk(chunk, base_args))

        return results

    def _apply_chunk(self, files: list[Path], base_args: list[str]) -> list[MP3GainFileResult]:
        try:
            result = self._runner([*base_args, *[str(file_path) for file_path in files]])
        except FileNotFoundError as exc:
            return [
                MP3GainFileResult(path=file_path, status=MP3GainStatus.FAILED, error=str(exc)) for file_path in files
            ]
        except Exception as exc:
            logger.warning("mp3gain invocation failed for %d files: %s", len(files), exc)
            return [
                MP3GainFileResult(
                    path=file_path,
                    status=MP3GainStatus.FAILED,
                    error=f"mp3gain Ausfuehrung fehlgeschlagen: {exc}",
                )
                for file_path in files
            ]

        if result.success and not self._has_file_open_error(result):
            return [MP3GainFileResult(path=file_path, status=MP3GainStatus.UPDATED) for file_path in files]

        if result.success and self._has_file_open_error(result) and len(files) == 1:
            return [
                MP3GainFileResult(
                    path=files[0],
                    status=MP3GainStatus.FAILED,
                    error=self._format_runner_error(result),
                )
            ]

        if result.success and self._has_file_open_error(result):
            isolated_results: list[MP3GainFileResult] = []
            for file_path in files:
                isolated_results.extend(self._apply_chunk([file_path], base_args))
            return isolated_results

        if len(files) == 1:
            return [
                MP3GainFileResult(
                    path=files[0],
                    status=MP3GainStatus.FAILED,
                    error=self._format_runner_error(result),
                )
            ]

        # If a batch fails, isolate the failing files to avoid aborting the whole library.
        isolated_results: list[MP3GainFileResult] = []
        for file_path in files:
            isolated_results.extend(self._apply_chunk([file_path], base_args))
        return isolated_results

    def _chunk_files(self, files: list[Path], base_args: list[str]) -> list[list[Path]]:
        base_length = len(" ".join(base_args)) + 16
        chunks: list[list[Path]] = []
        current_chunk: list[Path] = []
        current_length = base_length

        for file_path in files:
            token_length = len(str(file_path)) + 3
            if current_chunk and current_length + token_length > self._max_command_chars:
                chunks.append(current_chunk)
                current_chunk = [file_path]
                current_length = base_length + token_length
                continue

            current_chunk.append(file_path)
            current_length += token_length

        if current_chunk:
            chunks.append(current_chunk)

        return chunks

    @staticmethod
    def _build_base_args(album_mode: bool, target_db: float, prevent_clipping: bool) -> list[str]:
        args = ["-a" if album_mode else "-r"]
        if prevent_clipping:
            args.append("-k")

        gain_offset = round(target_db - 89.0, 1)
        if abs(gain_offset) >= 0.05:
            args.extend(["-d", f"{gain_offset:.1f}"])
        return args

    @staticmethod
    def _format_runner_error(result: MP3GainResult) -> str:
        stderr_tail = "\n".join(result.stderr.strip().splitlines()[-3:]).strip()
        stdout_tail = "\n".join(result.stdout.strip().splitlines()[-3:]).strip()

        if stderr_tail:
            return f"mp3gain Fehler (Code {result.return_code}): {stderr_tail}"
        if stdout_tail:
            return f"mp3gain Fehler (Code {result.return_code}): {stdout_tail}"
        return f"mp3gain Fehler (Code {result.return_code})."

    @staticmethod
    def _supports_mp3gain_path(file_path: Path) -> bool:
        # The classic Windows MP3Gain build uses ANSI path APIs and cannot open
        # paths with characters outside the local code page.
        if os.name != "nt":
            return True
        try:
            str(file_path).encode("cp1252")
        except UnicodeEncodeError:
            return False
        return True

    @staticmethod
    def _has_file_open_error(result: MP3GainResult) -> bool:
        output = f"{result.stdout}\n{result.stderr}".lower()
        return "can't open" in output or "cannot open" in output
