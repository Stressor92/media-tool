from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import patch

from utils.ytdlp_runner import DownloadResult, YtDlpError, YtDlpRunner


class _Completed:
    def __init__(self, returncode: int, stdout: str = "", stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_search_parses_json_lines() -> None:
    stdout = "\n".join(
        [
            '{"title":"Movie Official Trailer","id":"abc123","uploader":"Studio"}',
            "not-json",
            '{"title":"Another Trailer","webpage_url":"https://youtube.com/watch?v=xyz987"}',
        ]
    )

    with patch("utils.ytdlp_runner.subprocess.run", return_value=_Completed(0, stdout=stdout)):
        runner = YtDlpRunner(verify_installation=False)
        videos = runner.search("Movie trailer", max_results=2)

    assert len(videos) == 2
    assert videos[0].title == "Movie Official Trailer"
    assert videos[0].url.endswith("abc123")
    assert videos[1].url.endswith("xyz987")


def test_search_raises_error_on_nonzero_exit() -> None:
    with patch(
        "utils.ytdlp_runner.subprocess.run",
        return_value=_Completed(1, stderr="boom"),
    ):
        runner = YtDlpRunner(verify_installation=False)
        try:
            runner.search("Movie")
            assert False, "Expected YtDlpError"
        except YtDlpError as exc:
            assert "boom" in str(exc)


def test_download_finalizes_output_file(tmp_path: Path) -> None:
    output_file = tmp_path / "Movie (2020)-trailer.mp4"
    temp_file = tmp_path / "Movie (2020)-trailer-temp123.mp4"

    def _fake_run(*args: Any, **kwargs: Any) -> _Completed:
        del args, kwargs
        temp_file.write_bytes(b"trailer-data")
        return _Completed(0)

    with patch("utils.ytdlp_runner.subprocess.run", side_effect=_fake_run):
        runner = YtDlpRunner(verify_installation=False)
        result = runner.download("https://youtube.com/watch?v=abc", output_file)

    assert isinstance(result, DownloadResult)
    assert result.success is True
    assert result.file_path == output_file
    assert output_file.exists()
    assert output_file.read_bytes() == b"trailer-data"


def test_download_returns_error_on_failure(tmp_path: Path) -> None:
    output_file = tmp_path / "Movie (2020)-trailer.mp4"

    with patch(
        "utils.ytdlp_runner.subprocess.run",
        return_value=_Completed(1, stderr="download failed"),
    ):
        runner = YtDlpRunner(verify_installation=False)
        result = runner.download("https://youtube.com/watch?v=abc", output_file)

    assert result.success is False
    assert result.error is not None
    assert "download failed" in result.error
