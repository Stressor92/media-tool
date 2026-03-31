"""
src/utils/ffmpeg_runner.py

Low-level FFmpeg subprocess wrapper.
Responsibility: execute ffmpeg commands and return structured results.

Rules:
- No business logic here
- No CLI/UI concerns
- Always capture stderr
- Always validate return codes
"""

from __future__ import annotations

import subprocess
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from utils.config import get_config

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FFmpegResult:
    """Structured result returned from every ffmpeg invocation."""

    success: bool
    return_code: int
    command: list[str]
    stderr_bytes: bytes = b""
    stdout_bytes: bytes = b""

    @property
    def failed(self) -> bool:
        return not self.success
    
    @property
    def stderr(self) -> str:
        """Decoded stderr with safe error handling for non-ASCII chars."""
        return self.stderr_bytes.decode("utf-8", errors="replace")
    
    @property
    def stdout(self) -> str:
        """Decoded stdout with safe error handling for non-ASCII chars."""
        return self.stdout_bytes.decode("utf-8", errors="replace")


def run_ffmpeg(args: list[str]) -> FFmpegResult:
    """
    Execute an ffmpeg command via subprocess.

    Args:
        args: Full argument list, e.g. ["-y", "-i", "input.mp4", "-map", "0", ...]
              Do NOT include "ffmpeg" itself — it is prepended automatically.

    Returns:
        FFmpegResult with success flag, return code, and captured stderr/stdout (as bytes).

    Raises:
        FileNotFoundError: If ffmpeg is not installed / not on PATH.
    """
    command = [get_config().tools.ffmpeg] + args
    logger.debug(
        "Starting ffmpeg process",
        extra={
            "context": {
                "executable": command[0],
                "arg_count": len(args),
            }
        },
    )

    try:
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            # ✅ NO text=True, NO encoding - capture as bytes
        )
    except FileNotFoundError as exc:
        raise FileNotFoundError(
            f"ffmpeg executable not found: {command[0]}"
        ) from exc

    success = result.returncode == 0

    if not success:
        # Decode stderr safely for logging
        stderr_str = result.stderr.decode("utf-8", errors="replace")
        logger.warning(
            "ffmpeg process failed",
            extra={
                "context": {
                    "return_code": result.returncode,
                    "executable": command[0],
                    "arg_count": len(args),
                    "stderr_tail": stderr_str[-1000:],
                }
            },
        )
    else:
        logger.debug(
            "ffmpeg process succeeded",
            extra={
                "context": {
                    "executable": command[0],
                    "arg_count": len(args),
                }
            },
        )

    return FFmpegResult(
        success=success,
        return_code=result.returncode,
        command=command,
        stderr_bytes=result.stderr,
        stdout_bytes=result.stdout,
    )


@dataclass(frozen=True)
class MuxResult:
    success: bool
    output_file: Path
    error_message: Optional[str] = None


class FFmpegMuxer:
    """Safe MKV muxing operations."""

    @staticmethod
    def add_subtitle_to_mkv(
        mkv_path: Path,
        srt_path: Path,
        language: str = "eng",
        title: str = "English (Whisper AI)"
    ) -> MuxResult:
        if not mkv_path.exists():
            return MuxResult(success=False, output_file=mkv_path, error_message="MKV file does not exist")
        if not srt_path.exists():
            return MuxResult(success=False, output_file=mkv_path, error_message="SRT file does not exist")

        backup_file = mkv_path.with_suffix(mkv_path.suffix + ".backup")
        mkv_temp = mkv_path.with_suffix(".tmp.mkv")

        try:
            # Use shutil.move so the rename succeeds on Windows even if an
            # existing .backup file was left by a previous run or by the
            # caller's own backup step.
            import shutil as _shutil
            _shutil.move(str(mkv_path), str(backup_file))

            cmd = [
                "-y",
                "-i", str(backup_file),
                "-i", str(srt_path),
                "-map", "0",
                "-map", "1",
                "-c", "copy",
                "-c:s", "srt",
                "-metadata:s:s:0", f"language={language}",
                "-metadata:s:s:0", f"title={title}",
                str(mkv_temp)
            ]

            result = run_ffmpeg(cmd)
            if not result.success:
                backup_file.rename(mkv_path)
                return MuxResult(success=False, output_file=mkv_path, error_message=f"ffmpeg mux failed: {result.stderr}")

            # Validate size
            orig_size = backup_file.stat().st_size
            out_size = mkv_temp.stat().st_size
            if out_size < orig_size * 0.90 or out_size > orig_size * 1.10:
                # rollback
                mkv_temp.unlink(missing_ok=True)
                backup_file.rename(mkv_path)
                return MuxResult(success=False, output_file=mkv_path, error_message="Mux output size out of expected range")

            mkv_temp.replace(mkv_path)
            backup_file.unlink(missing_ok=True)
            return MuxResult(success=True, output_file=mkv_path)

        except Exception as exc:
            # recover
            if backup_file.exists() and not mkv_path.exists():
                backup_file.rename(mkv_path)
            return MuxResult(success=False, output_file=mkv_path, error_message=str(exc))

