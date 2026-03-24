"""
src/utils/ffprobe_runner.py

Low-level ffprobe subprocess wrapper.
Responsibility: run ffprobe and return parsed JSON or raw output.

Rules:
- No business logic
- No CLI/UI concerns
- Always validate return codes
- Always capture stderr
"""

from __future__ import annotations

import json
import subprocess
import logging
from dataclasses import dataclass
from pathlib import Path

from utils.config import get_config

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ProbeResult:
    """Structured result from an ffprobe invocation."""

    success: bool
    return_code: int
    data: dict          # parsed JSON (empty dict on failure)
    stderr: str

    @property
    def failed(self) -> bool:
        return not self.success

    def __getitem__(self, key: str) -> object:
        return self.data[key]

    def get(self, key: str, default: object = None) -> object:
        return self.data.get(key, default)

    # ------------------------------------------------------------------
    # Convenience accessors
    # ------------------------------------------------------------------

    @property
    def streams(self) -> list[dict]:
        return self.data.get("streams", [])

    @property
    def format(self) -> dict:
        return self.data.get("format", {})

    def video_streams(self) -> list[dict]:
        return [s for s in self.streams if s.get("codec_type") == "video"]

    def audio_streams(self) -> list[dict]:
        return [s for s in self.streams if s.get("codec_type") == "audio"]

    def subtitle_streams(self) -> list[dict]:
        return [s for s in self.streams if s.get("codec_type") == "subtitle"]

    def first_video(self) -> dict | None:
        vs = self.video_streams()
        return vs[0] if vs else None


def probe_file(path: Path) -> ProbeResult:
    """
    Run ffprobe on a media file and return parsed JSON stream/format data.

    Args:
        path: Path to the media file to analyse.

    Returns:
        ProbeResult with parsed data dict and success flag.

    Raises:
        FileNotFoundError: If ffprobe is not installed / not on PATH.
    """
    command = [
        get_config().tools.ffprobe,
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        str(path),
    ]

    logger.debug("Running ffprobe: %s", " ".join(command))

    try:
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            # ✅ NO text=True - capture as bytes
        )
    except FileNotFoundError as exc:
        raise FileNotFoundError(
            f"ffprobe executable not found: {command[0]}"
        ) from exc

    # Decode stderr safely for error reporting
    stderr_str = result.stderr.decode("utf-8", errors="replace")
    
    if result.returncode != 0:
        logger.warning(
            "ffprobe failed (exit %d) on %s:\n%s",
            result.returncode,
            path,
            stderr_str[-1000:],
        )
        return ProbeResult(
            success=False,
            return_code=result.returncode,
            data={},
            stderr=stderr_str,
        )

    try:
        # Decode stdout safely and parse JSON
        stdout_str = result.stdout.decode("utf-8", errors="replace")
        data = json.loads(stdout_str)
    except json.JSONDecodeError as exc:
        logger.error("ffprobe returned invalid JSON for %s: %s", path, exc)
        return ProbeResult(
            success=False,
            return_code=result.returncode,
            data={},
            stderr=f"JSON parse error: {exc}",
        )

    return ProbeResult(
        success=True,
        return_code=result.returncode,
        data=data,
        stderr=stderr_str,
    )


def probe_cropdetect(path: Path, skip_seconds: int = 5, sample_seconds: int = 10) -> str | None:
    """
    Run ffmpeg's cropdetect filter on a short segment of the video.

    Returns the last detected crop string (e.g. "crop=704:576:8:0"),
    or None if no crop was detected or the detection failed.

    Args:
        path:           Path to the video file.
        skip_seconds:   How many seconds to skip at the start.
        sample_seconds: How many seconds to analyse for crop detection.
    """
    command = [
        get_config().tools.ffmpeg,
        "-ss", str(skip_seconds),
        "-t",  str(sample_seconds),
        "-i", str(path),
        "-vf", "cropdetect=24:16:1",
        "-f", "null", "-",
    ]

    logger.debug("Running cropdetect: %s", " ".join(command))

    try:
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            # ✅ NO text=True - capture as bytes
        )
    except FileNotFoundError as exc:
        raise FileNotFoundError(
            f"ffmpeg executable not found: {command[0]}"
        ) from exc

    # Decode stderr safely for crop detection output
    stderr_str = result.stderr.decode("utf-8", errors="replace")
    crop_lines = [
        line for line in stderr_str.splitlines()
        if "crop=" in line
    ]

    if not crop_lines:
        return None

    # Take the last detected value (most stable)
    last = crop_lines[-1]
    # Extract crop=W:H:X:Y
    import re
    match = re.search(r"crop=\d+:\d+:\d+:\d+", last)
    return match.group(0) if match else None
