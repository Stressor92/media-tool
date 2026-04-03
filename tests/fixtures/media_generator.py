"""
tests/fixtures/media_generator.py

Generate VALID test media using FFmpeg.
Creates real video,audio, and subtitle files that pass FFprobe validation.

This replaces test files created with dummy binary data, which fail
when tests call ffprobe or real validation logic.
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


class TestMediaGenerator:
    """Generate VALID test media using FFmpeg."""

    @staticmethod
    def create_test_video(
        output_path: Path,
        duration: float = 5.0,
        resolution: tuple[int, int] = (1280, 720),
        with_audio: bool = True,
        with_subtitles: bool = False,
        preset: str = "ultrafast",
    ) -> Path:
        """
        Generate valid video file using FFmpeg.

        Args:
            output_path: Where to save video file (MKV or MP4)
            duration: Video length in seconds
            resolution: (width, height) tuple
            with_audio: Include audio track
            with_subtitles: Include subtitle track (creates SRT file)
            preset: FFmpeg preset (ultrafast/superfast for tests)

        Returns:
            Path to generated video file

        Raises:
            RuntimeError: If generation or validation fails
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Build FFmpeg command
        cmd = [
            "ffmpeg",
            "-y",  # Overwrite output
            "-f",
            "lavfi",
            "-i",
            f"testsrc=duration={duration}:size={resolution[0]}x{resolution[1]}:rate=30",
        ]

        # Add audio input if requested
        if with_audio:
            cmd.extend(["-f", "lavfi", "-i", f"sine=frequency=1000:duration={duration}"])

        # Add subtitle input if requested
        if with_subtitles:
            srt_path = output_path.with_stem(output_path.stem + "_subs").with_suffix(".srt")
            srt_path.write_text("1\n00:00:00,000 --> 00:00:05,000\nTest subtitle\n")
            cmd.extend(["-i", str(srt_path)])

        # Video codec options
        cmd.extend(["-c:v", "libx264", "-preset", preset, "-pix_fmt", "yuv420p"])

        # Audio codec options
        if with_audio:
            cmd.extend(["-c:a", "aac", "-b:a", "128k"])
        else:
            cmd.extend(["-an"])

        # Subtitle codec options
        if with_subtitles:
            cmd.extend(["-c:s", "move_text"])

        # Duration and output
        cmd.extend(["-t", str(duration), "-loglevel", "error", str(output_path)])

        # Run FFmpeg
        logger.debug(f"Running: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True)

        if result.returncode != 0:
            error_msg = result.stderr.decode("utf-8", errors="ignore")
            raise RuntimeError(f"FFmpeg failed to generate video: {error_msg}")

        # Verify file was created
        if not output_path.exists():
            raise RuntimeError(f"Generated file not found: {output_path}")

        # Validate with ffprobe
        TestMediaGenerator._validate_with_ffprobe(output_path)

        logger.debug(f"Generated valid video: {output_path} ({output_path.stat().st_size} bytes)")
        return output_path

    @staticmethod
    def create_test_audio(output_path: Path, duration: float = 10.0, sample_rate: int = 16000) -> Path:
        """
        Generate valid audio file (MP3 or WAV).

        Args:
            output_path: Where to save audio file
            duration: Audio length in seconds
            sample_rate: Sample rate in Hz

        Returns:
            Path to generated audio file
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        cmd = [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency=1000:duration={duration}",
            "-ar",
            str(sample_rate),
            "-loglevel",
            "error",
            str(output_path),
        ]

        result = subprocess.run(cmd, capture_output=True)

        if result.returncode != 0:
            error_msg = result.stderr.decode("utf-8", errors="ignore")
            raise RuntimeError(f"FFmpeg failed to generate audio: {error_msg}")

        TestMediaGenerator._validate_with_ffprobe(output_path)
        return output_path

    @staticmethod
    def create_large_file(output_path: Path, size_bytes: int = 131072) -> Path:
        """
        Create file large enough for hash calculations.

        OpenSubtitles hash requires minimum 128KB.

        Args:
            output_path: Where to save file
            size_bytes: File size in bytes (default 128KB)

        Returns:
            Path to created file
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "wb") as f:
            # Write in chunks to be more efficient
            chunk_size = 8192
            remaining = size_bytes
            while remaining > 0:
                chunk = min(chunk_size, remaining)
                f.write(b"\x00" * chunk)
                remaining -= chunk

        actual_size = output_path.stat().st_size
        if actual_size < size_bytes:
            raise RuntimeError(f"Failed to create file with required size. Expected {size_bytes}, got {actual_size}")

        logger.debug(f"Created binary file: {output_path} ({actual_size} bytes)")
        return output_path

    @staticmethod
    def _validate_with_ffprobe(file_path: Path) -> bool:
        """
        Validate file with ffprobe.

        Args:
            file_path: File to validate

        Returns:
            True if valid

        Raises:
            RuntimeError: If file is invalid
        """
        cmd = [
            "ffprobe",
            "-v",
            "error",
            "-show_streams",
            str(file_path),
        ]

        result = subprocess.run(cmd, capture_output=True)

        if result.returncode != 0:
            error_msg = result.stderr.decode("utf-8", errors="ignore")
            raise RuntimeError(f"FFprobe validation failed: {error_msg}")

        return True

    @staticmethod
    def create_srt_file(output_path: Path, num_subtitles: int = 3) -> Path:
        """
        Create valid SRT subtitle file.

        Args:
            output_path: Where to save SRT file
            num_subtitles: Number of subtitle entries

        Returns:
            Path to created SRT file
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        lines = []
        for i in range(1, num_subtitles + 1):
            start_time = (i - 1) * 5
            end_time = i * 5
            lines.append(f"{i}")
            lines.append(f"00:00:{start_time:02d},000 --> 00:00:{end_time:02d},000")
            lines.append(f"Subtitle line {i}")
            lines.append("")

        output_path.write_text("\n".join(lines))
        return output_path
