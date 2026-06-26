from __future__ import annotations

from unittest.mock import patch

from core.audiobook.silence_cleanup import remove_long_silence, remove_long_silence_in_library
from utils.ffmpeg_runner import FFmpegResult


def test_remove_long_silence_builds_silenceremove_filter(tmp_path):
    input_file = tmp_path / "input.m4b"
    output_file = tmp_path / "output.m4b"
    input_file.touch()

    with patch("core.audiobook.silence_cleanup.run_ffmpeg") as mock_ffmpeg:
        mock_ffmpeg.return_value = FFmpegResult(
            success=True,
            return_code=0,
            command=["ffmpeg"],
            stderr_bytes=b"",
            stdout_bytes=b"",
        )

        result = remove_long_silence(
            input_file=input_file,
            output_file=output_file,
            min_silence_seconds=10.0,
            silence_threshold_db=-45.0,
            overwrite=True,
        )

        assert result.success is True
        args = mock_ffmpeg.call_args.args[0]
        command_text = " ".join(args)
        assert "silenceremove=" in command_text
        assert "stop_periods=-1" in command_text
        assert "stop_duration=10.0" in command_text
        assert "-map_metadata" in args


def test_remove_long_silence_in_library_counts(tmp_path):
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / "a.m4b").touch()
    (source_dir / "b.mp3").touch()

    target_dir = tmp_path / "target"

    with patch("core.audiobook.silence_cleanup.run_ffmpeg") as mock_ffmpeg:
        mock_ffmpeg.return_value = FFmpegResult(
            success=True,
            return_code=0,
            command=["ffmpeg"],
            stderr_bytes=b"",
            stdout_bytes=b"",
        )

        counts = remove_long_silence_in_library(
            input_dir=source_dir,
            output_dir=target_dir,
            min_silence_seconds=10.0,
            silence_threshold_db=-50.0,
            recursive=True,
            overwrite=True,
        )

        assert counts["processed"] == 2
        assert counts["cleaned"] == 2
        assert counts["errors"] == 0
