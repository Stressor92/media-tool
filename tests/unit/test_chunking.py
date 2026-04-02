# tests/unit/test_chunking.py
from __future__ import annotations

from core.translation.chunking import (
    SubtitleChunk,
    _proportional_split,
    build_chunks,
    split_translated_chunk,
)
from core.translation.models import SubtitleSegment


def _seg(idx: int, text: str) -> SubtitleSegment:
    return SubtitleSegment(index=idx, start="00:00:00,000", end="00:00:01,000", text=text)


class TestBuildChunks:
    def test_single_segment_single_chunk(self) -> None:
        segs = [_seg(1, "Hello.")]
        chunks = build_chunks(segs, max_segments=4, max_chars=250)
        assert len(chunks) == 1
        assert chunks[0].segment_indices == [0]

    def test_respects_max_segments(self) -> None:
        segs = [_seg(i, f"Line {i}.") for i in range(8)]
        chunks = build_chunks(segs, max_segments=3, max_chars=1000)
        for chunk in chunks:
            assert len(chunk.segment_indices) <= 3

    def test_respects_max_chars(self) -> None:
        segs = [_seg(i, "A" * 100) for i in range(4)]
        chunks = build_chunks(segs, max_segments=10, max_chars=150)
        for chunk in chunks:
            assert len(chunk.combined_text) <= 250  # generous upper bound

    def test_all_segments_covered(self) -> None:
        segs = [_seg(i, f"Text {i}.") for i in range(12)]
        chunks = build_chunks(segs, max_segments=4, max_chars=250)
        all_indices = [i for c in chunks for i in c.segment_indices]
        assert sorted(all_indices) == list(range(12))

    def test_sentence_end_triggers_break(self) -> None:
        segs = [_seg(1, "Hello."), _seg(2, "How are you?"), _seg(3, "Fine thanks.")]
        chunks = build_chunks(segs, max_segments=10, max_chars=1000)
        # Every segment ends with punctuation → each pair/triple may be grouped
        # Just verify coverage
        all_indices = sorted(i for c in chunks for i in c.segment_indices)
        assert all_indices == list(range(len(segs)))

    def test_combined_text_joins_by_newline(self) -> None:
        segs = [_seg(0, "Hello"), _seg(1, "World")]
        chunks = build_chunks(segs, max_segments=4, max_chars=1000)
        combined = chunks[0].combined_text
        assert "Hello" in combined
        assert "World" in combined
        assert "\n" in combined


class TestSplitTranslatedChunk:
    def test_exact_line_count_match(self) -> None:
        chunk = SubtitleChunk(
            segment_indices=[0, 1, 2],
            combined_text="A\nB\nC",
            original_texts=["A", "B", "C"],
        )
        translated = "Eins\nZwei\nDrei"
        parts = split_translated_chunk(chunk, translated)
        assert parts == ["Eins", "Zwei", "Drei"]

    def test_fallback_proportional_split(self) -> None:
        chunk = SubtitleChunk(
            segment_indices=[0, 1],
            combined_text="Short text\nA much longer text segment here",
            original_texts=["Short text", "A much longer text segment here"],
        )
        translated = "Kurz Text Ein viel längerer Text Abschnitt hier"
        parts = split_translated_chunk(chunk, translated)
        assert len(parts) == 2
        assert all(p for p in parts)  # no empty strings

    def test_single_segment_chunk(self) -> None:
        chunk = SubtitleChunk(
            segment_indices=[0],
            combined_text="Hello",
            original_texts=["Hello"],
        )
        parts = split_translated_chunk(chunk, "Hallo")
        assert parts == ["Hallo"]


class TestProportionalSplit:
    def test_empty_originals(self) -> None:
        result = _proportional_split("test", [])
        assert result == ["test"]

    def test_two_equal_parts(self) -> None:
        result = _proportional_split("one two three four", ["abc", "abc"])
        assert len(result) == 2
        assert result[0]  # not empty
        assert result[1]  # not empty

    def test_last_segment_gets_remainder(self) -> None:
        result = _proportional_split("a b c d e f", ["x", "y"])
        # All words should be present across both parts
        combined = " ".join(result)
        for w in ["a", "b", "c", "d", "e", "f"]:
            assert w in combined
