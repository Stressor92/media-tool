import pytest

from core.metadata.match_selector import MatchSelector, SelectionMode
from core.metadata.models import TmdbSearchResult


def _result(tmdb_id: int, title: str) -> TmdbSearchResult:
    return TmdbSearchResult(
        tmdb_id=tmdb_id,
        title=title,
        original_title=title,
        year=2010,
        overview="",
        popularity=0.0,
        vote_average=0.0,
        vote_count=0,
        poster_path=None,
        backdrop_path=None,
    )


def test_auto_mode_selects_first_result() -> None:
    selector = MatchSelector(mode=SelectionMode.AUTO)

    selected = selector.select([_result(1, "A"), _result(2, "B")], "A", 2010)

    assert selected.selected is not None
    assert selected.selected.tmdb_id == 1
    assert selected.mode == SelectionMode.AUTO
    assert selected.was_manual is False


def test_select_returns_none_for_empty_results() -> None:
    selector = MatchSelector(mode=SelectionMode.AUTO)

    selected = selector.select([], "Missing", None)

    assert selected.selected is None
    assert selected.skipped is False


def test_interactive_mode_can_skip(monkeypatch: pytest.MonkeyPatch) -> None:
    selector = MatchSelector(mode=SelectionMode.INTERACTIVE)

    monkeypatch.setattr("typer.echo", lambda *args, **kwargs: None)
    monkeypatch.setattr("typer.prompt", lambda *args, **kwargs: "0")

    selected = selector.select([_result(1, "A")], "A", 2010)

    assert selected.selected is None
    assert selected.mode == SelectionMode.INTERACTIVE
    assert selected.skipped is True


def test_interactive_mode_retries_invalid_then_selects(monkeypatch: pytest.MonkeyPatch) -> None:
    selector = MatchSelector(mode=SelectionMode.INTERACTIVE)
    prompts = iter(["invalid", "3", "2"])

    monkeypatch.setattr("typer.echo", lambda *args, **kwargs: None)
    monkeypatch.setattr("typer.prompt", lambda *args, **kwargs: next(prompts))

    selected = selector.select([_result(1, "A"), _result(2, "B")], "A", 2010)

    assert selected.selected is not None
    assert selected.selected.tmdb_id == 2
    assert selected.was_manual is True
