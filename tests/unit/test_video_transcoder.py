from __future__ import annotations

from pathlib import Path

from core.video.models import EncoderType
from core.video.transcoder import (
    BatchTranscodeSummary,
    TranscodeOptions,
    TranscodeStatus,
    batch_transcode_to_h265,
    transcode_to_h265,
)
from utils.ffmpeg_runner import FFmpegResult


class _FakeProbe:
    def __init__(self, codec_name: str, failed: bool = False) -> None:
        self.failed = failed
        self._codec_name = codec_name

    def first_video(self) -> dict[str, str]:
        return {"codec_name": self._codec_name}


class _FakeEncoderParams:
    def __init__(self, encoder: str, encoder_type: EncoderType, base_args: list[str]) -> None:
        self.encoder = encoder
        self.encoder_type = encoder_type
        self.base_args = base_args
        self.profile_name = "brrip"


def _ok_ffmpeg_result(command: list[str] | None = None) -> FFmpegResult:
    return FFmpegResult(
        success=True,
        return_code=0,
        command=command or ["ffmpeg"],
        stderr_bytes=b"",
        stdout_bytes=b"",
    )


def _fail_ffmpeg_result(command: list[str] | None = None) -> FFmpegResult:
    return FFmpegResult(
        success=False,
        return_code=1,
        command=command or ["ffmpeg"],
        stderr_bytes=b"failed",
        stdout_bytes=b"",
    )


def test_transcode_success_copies_non_video_streams(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "movie.mkv"
    source.write_bytes(b"x" * 4096)
    target = tmp_path / "movie.h265.mkv"

    monkeypatch.setattr("core.video.transcoder.probe_file", lambda _p: _FakeProbe("h264"))
    monkeypatch.setattr(
        "core.video.transcoder._build_encoder_params",
        lambda _opts: _FakeEncoderParams("libx265", EncoderType.SOFTWARE, ["-c:v", "libx265", "-crf", "21"]),
    )

    captured_args: dict[str, list[str]] = {}

    def _fake_run_ffmpeg(args: list[str]) -> FFmpegResult:
        captured_args["args"] = args
        target.write_bytes(b"ok")
        return _ok_ffmpeg_result(["ffmpeg", *args])

    monkeypatch.setattr("core.video.transcoder.run_ffmpeg", _fake_run_ffmpeg)

    result = transcode_to_h265(source=source, target=target, opts=TranscodeOptions())

    assert result.status == TranscodeStatus.SUCCESS
    assert target.exists()
    args = captured_args["args"]
    assert "-map" in args
    assert "0" in args
    assert "-c:v" in args
    assert "-c:a" in args
    assert "copy" in args
    assert "-c:s" in args
    assert "-map_metadata" in args
    assert "-map_chapters" in args


def test_transcode_skips_hevc_by_default(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "movie.mkv"
    source.write_bytes(b"x" * 1024)

    monkeypatch.setattr("core.video.transcoder.probe_file", lambda _p: _FakeProbe("hevc"))

    result = transcode_to_h265(source=source, opts=TranscodeOptions(skip_if_hevc=True))

    assert result.status == TranscodeStatus.SKIPPED
    assert "Already HEVC" in result.message


def test_transcode_can_reencode_hevc_when_requested(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "movie.mkv"
    source.write_bytes(b"x" * 4096)
    target = tmp_path / "movie.h265.mkv"

    monkeypatch.setattr("core.video.transcoder.probe_file", lambda _p: _FakeProbe("hevc"))
    monkeypatch.setattr(
        "core.video.transcoder._build_encoder_params",
        lambda _opts: _FakeEncoderParams("libx265", EncoderType.SOFTWARE, ["-c:v", "libx265", "-crf", "21"]),
    )

    def _fake_run_ffmpeg(_args: list[str]) -> FFmpegResult:
        target.write_bytes(b"ok")
        return _ok_ffmpeg_result()

    monkeypatch.setattr("core.video.transcoder.run_ffmpeg", _fake_run_ffmpeg)

    result = transcode_to_h265(source=source, target=target, opts=TranscodeOptions(skip_if_hevc=False))

    assert result.status == TranscodeStatus.SUCCESS


def test_transcode_hardware_fallback_to_software(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "movie.mkv"
    source.write_bytes(b"x" * 4096)
    target = tmp_path / "movie.h265.mkv"

    monkeypatch.setattr("core.video.transcoder.probe_file", lambda _p: _FakeProbe("h264"))

    calls = {"n": 0}

    def _fake_build_encoder_params(opts: TranscodeOptions) -> _FakeEncoderParams:
        if opts.force_software:
            return _FakeEncoderParams("libx265", EncoderType.SOFTWARE, ["-c:v", "libx265", "-crf", "21"])
        return _FakeEncoderParams("hevc_nvenc", EncoderType.NVENC, ["-c:v", "hevc_nvenc", "-cq", "22"])

    monkeypatch.setattr("core.video.transcoder._build_encoder_params", _fake_build_encoder_params)

    def _fake_run_ffmpeg(_args: list[str]) -> FFmpegResult:
        calls["n"] += 1
        if calls["n"] == 1:
            return _fail_ffmpeg_result()
        target.write_bytes(b"ok")
        return _ok_ffmpeg_result()

    monkeypatch.setattr("core.video.transcoder.run_ffmpeg", _fake_run_ffmpeg)

    result = transcode_to_h265(source=source, target=target, opts=TranscodeOptions(hw_fallback_on_error=True))

    assert calls["n"] == 2
    assert result.status == TranscodeStatus.SUCCESS
    assert "software fallback" in result.message


def test_batch_transcode_collects_results(tmp_path: Path, monkeypatch) -> None:
    directory = tmp_path / "movies"
    directory.mkdir()
    (directory / "a.mkv").write_bytes(b"x" * 1024)
    (directory / "b.mp4").write_bytes(b"x" * 1024)
    (directory / "ignore.txt").write_text("x", encoding="utf-8")

    monkeypatch.setattr("core.video.transcoder.probe_file", lambda _p: _FakeProbe("h264"))
    monkeypatch.setattr(
        "core.video.transcoder._build_encoder_params",
        lambda _opts: _FakeEncoderParams("libx265", EncoderType.SOFTWARE, ["-c:v", "libx265", "-crf", "21"]),
    )
    monkeypatch.setattr("core.video.transcoder.run_ffmpeg", lambda _args: _ok_ffmpeg_result())

    summary = batch_transcode_to_h265(directory, opts=TranscodeOptions(recursive=False))

    assert isinstance(summary, BatchTranscodeSummary)
    assert summary.total == 2
    assert len(summary.succeeded) == 2
