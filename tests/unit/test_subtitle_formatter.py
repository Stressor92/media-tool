# tests/unit/test_subtitle_formatter.py
from __future__ import annotations

from core.translation.subtitle_formatter import format_subtitle


class TestFormatSubtitle:
    def test_short_text_unchanged(self) -> None:
        assert format_subtitle("Hello world") == "Hello world"

    def test_long_text_wrapped(self) -> None:
        text = "Das ist ein sehr langer Satz der nicht gut lesbar ist"
        result = format_subtitle(text, max_chars=30, max_lines=2)
        lines = result.split("\n")
        assert len(lines) == 2

    def test_max_two_lines_enforced(self) -> None:
        text = "one two three four five six seven eight nine ten eleven twelve"
        result = format_subtitle(text, max_chars=20, max_lines=2)
        lines = result.split("\n")
        assert len(lines) <= 2

    def test_each_line_within_limit_when_possible(self) -> None:
        text = "Das ist ein sehr langer Satz der nicht gut lesbar ist"
        result = format_subtitle(text, max_chars=30, max_lines=2)
        for line in result.split("\n")[:-1]:  # last line may overflow
            assert len(line) <= 30

    def test_existing_newline_handled(self) -> None:
        text = "Short line\nAnother short line"
        result = format_subtitle(text, max_chars=40, max_lines=2)
        assert "Short" in result
        assert "Another" in result

    def test_single_word_longer_than_max_not_truncated(self) -> None:
        text = "Superlongwordthatcannotbesplit"
        result = format_subtitle(text, max_chars=10, max_lines=2)
        assert "Superlongwordthatcannotbesplit" in result

    def test_empty_string(self) -> None:
        assert format_subtitle("") == ""
