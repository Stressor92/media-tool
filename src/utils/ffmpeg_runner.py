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
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FFmpegResult:
    """Structured result returned from every ffmpeg invocation."""

    success: bool
    return_code: int
    command: list[str]
    stderr: str
    stdout: str = ""

    @property
    def failed(self) -> bool:
        return not self.success


def run_ffmpeg(args: list[str]) -> FFmpegResult:
    """
    Execute an ffmpeg command via subprocess.

    Args:
        args: Full argument list, e.g. ["-y", "-i", "input.mp4", "-map", "0", ...]
              Do NOT include "ffmpeg" itself — it is prepended automatically.

    Returns:
        FFmpegResult with success flag, return code, and captured stderr/stdout.

    Raises:
        FileNotFoundError: If ffmpeg is not installed / not on PATH.
    """
    command = ["ffmpeg"] + args
    logger.debug("Running ffmpeg: %s", " ".join(command))

    try:
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except FileNotFoundError as exc:
        raise FileNotFoundError(
            "ffmpeg executable not found. Is it installed and on PATH?"
        ) from exc

    success = result.returncode == 0

    if not success:
        logger.warning(
            "ffmpeg exited with code %d.\nCommand: %s\nStderr: %s",
            result.returncode,
            " ".join(command),
            result.stderr[-2000:],  # tail to avoid huge logs
        )

    return FFmpegResult(
        success=success,
        return_code=result.returncode,
        command=command,
        stderr=result.stderr,
        stdout=result.stdout,
    )
