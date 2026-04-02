# tests/unit/test_tag_processor.py
from __future__ import annotations

from core.translation.tag_processor import TagProcessor


class TestTagProcessorExtract:
    def test_no_tags_unchanged(self) -> None:
        tp = TagProcessor()
        result = tp.extract("Hello world")
        assert result.clean_text == "Hello world"
        assert result.mappings == []

    def test_html_tag_replaced_with_placeholder(self) -> None:
        tp = TagProcessor()
        result = tp.extract("<i>Hello</i>")
        assert "<i>" not in result.clean_text
        assert "</i>" not in result.clean_text
        assert len(result.mappings) == 2

    def test_ass_tag_replaced(self) -> None:
        tp = TagProcessor()
        result = tp.extract("{\\an8}Hello")
        assert "{\\an8}" not in result.clean_text
        assert len(result.mappings) == 1

    def test_multiple_html_tags(self) -> None:
        tp = TagProcessor()
        result = tp.extract("<b>Bold</b> and <i>italic</i>")
        assert len(result.mappings) == 4

    def test_placeholder_numbering_sequential(self) -> None:
        tp = TagProcessor()
        result = tp.extract("<i>A</i> <b>B</b>")
        names = [m.placeholder for m in result.mappings]
        assert names == ["__T0__", "__T1__", "__T2__", "__T3__"]

    def test_has_tags_true(self) -> None:
        tp = TagProcessor()
        assert tp.has_tags("<i>test</i>") is True

    def test_has_tags_false(self) -> None:
        tp = TagProcessor()
        assert tp.has_tags("plain text") is False


class TestTagProcessorRestore:
    def test_roundtrip_html(self) -> None:
        tp = TagProcessor()
        result = tp.extract("<i>Hello</i>")
        restored = tp.restore(result.clean_text.replace("Hello", "Hallo"), result.mappings)
        assert "<i>" in restored
        assert "</i>" in restored
        assert "Hallo" in restored

    def test_missing_placeholder_silently_dropped(self) -> None:
        tp = TagProcessor()
        result = tp.extract("<i>Hello</i>")
        # Translator drops all placeholders
        restored = tp.restore("Hallo", result.mappings)
        # Should not crash; result should just not contain tags
        assert "Hallo" in restored

    def test_no_mappings_returns_original(self) -> None:
        tp = TagProcessor()
        assert tp.restore("Hallo Welt", []) == "Hallo Welt"
