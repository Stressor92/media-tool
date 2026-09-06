"""
src/utils/mp3gain_runner.py

Low-level MP3Gain subprocess wrapper.
Responsibility: execute mp3gain commands and return structured results.
"""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass

from utils.config import get_config

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MP3GainResult:
    """Structured result returned from every mp3gain invocation."""

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
        return self.stderr_bytes.decode("utf-8", errors="replace")

    @property
    def stdout(self) -> str:
        return self.stdout_bytes.decode("utf-8", errors="replace")


def run_mp3gain(args: list[str]) -> MP3GainResult:
    """Execute an mp3gain command via subprocess."""
    command = [get_config().tools.mp3gain] + args

    try:
        result = subprocess.run(command, capture_output=True)
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"mp3gain executable not found: {command[0]}") from exc

    return_code = result.returncode
    if return_code > 0x7FFFFFFF:
        return_code -= 0x100000000

    success = return_code == 0
    if not success:
        logger.warning(
            "mp3gain process failed",
            extra={
                "context": {
                    "return_code": return_code,
                    "executable": command[0],
                    "stderr_tail": result.stderr.decode("utf-8", errors="replace")[-1000:],
                }
            },
        )

    return MP3GainResult(
        success=success,
        return_code=return_code,
        command=command,
        stderr_bytes=result.stderr,
        stdout_bytes=result.stdout,
    )
