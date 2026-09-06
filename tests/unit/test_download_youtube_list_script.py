"""Unit tests for scripts/download_youtube_list.py."""

from __future__ import annotations

import runpy
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast


def _load_script_namespace() -> dict[str, Any]:
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "download_youtube_list.py"
    return runpy.run_path(str(script_path))


def test_extract_urls_handles_mixed_formats_and_dedup() -> None:
    namespace = _load_script_namespace()
    extract_urls = cast(Callable[[str], list[str]], namespace["extract_urls"])

    raw = (
        "[a](https://www.youtube.com/watch?v=abc&list=PL1)\n"
        "https://www.youtube.com/watch?v=def&list=PL2\n"
        "https://www.youtube.com/watch?v=abc&list=PL1\n"
        "https://www.youtube.com/watch?v=ghi&list=PL3https://www.youtube.com/watch?v=ghi&list=PL3\n"
        "https://example.com/not-youtube\n"
    )

    assert extract_urls(raw) == [
        "https://www.youtube.com/watch?v=abc&list=PL1",
        "https://www.youtube.com/watch?v=def&list=PL2",
        "https://www.youtube.com/watch?v=ghi&list=PL3",
    ]


def test_main_uses_series_with_firefox_cookies(monkeypatch: Any) -> None:
    namespace = _load_script_namespace()
    main = cast(Callable[[], int], namespace["main"])
    globals_ref = main.__globals__

    globals_ref["RAW_LINK_INPUT"] = "https://www.youtube.com/watch?v=abc&list=PL1"
    globals_ref["DELAY_SECONDS"] = 0
    globals_ref["resolve_media_tool_executable"] = lambda: "media-tool"

    calls: list[list[str]] = []

    def _fake_run(command: list[str], check: bool) -> None:
        assert check is True
        calls.append(command)

    monkeypatch.setattr(globals_ref["subprocess"], "run", _fake_run)
    monkeypatch.setattr(globals_ref["time"], "sleep", lambda _seconds: None)

    assert main() == 0
    assert len(calls) == 1
    assert calls[0][0:3] == ["media-tool", "download", "series"]
    assert calls[0][3] == "https://www.youtube.com/watch?v=abc&list=PL1"
    assert calls[0][4:6] == ["--format", "mp3"]
    assert calls[0][6:8] == ["--cookies-from-browser", "firefox"]
