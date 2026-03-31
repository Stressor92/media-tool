from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto

from core.metadata.models import TmdbSearchResult


class SelectionMode(Enum):
    AUTO = auto()
    INTERACTIVE = auto()


@dataclass
class SelectionResult:
    selected: TmdbSearchResult | None
    mode: SelectionMode
    was_manual: bool = False
    skipped: bool = False


class MatchSelector:
    def __init__(self, mode: SelectionMode = SelectionMode.AUTO) -> None:
        self._mode = mode

    def select(
        self,
        results: list[TmdbSearchResult],
        title: str,
        year: int | None,
    ) -> SelectionResult:
        if not results:
            return SelectionResult(selected=None, mode=self._mode)
        if self._mode == SelectionMode.AUTO:
            return SelectionResult(selected=results[0], mode=SelectionMode.AUTO)
        return self._interactive_select(results, title, year)

    def _interactive_select(
        self,
        results: list[TmdbSearchResult],
        title: str,
        year: int | None,
    ) -> SelectionResult:
        import typer

        year_hint = str(year) if year else "?"
        typer.echo(f"\nTMDB results for '{title}' ({year_hint}):\n")
        typer.echo(f"  {'#':<4} {'Title':<45} {'Year':<6} {'Rating':<10} TMDB-ID")
        typer.echo("  " + "-" * 75)

        for index, result in enumerate(results, start=1):
            item_year = str(result.year) if result.year else "-"
            rating = f"{result.vote_average:.1f}" if result.vote_average else "-"
            typer.echo(
                f"  {index:<4} {result.title:<45} {item_year:<6} {rating:<10} {result.tmdb_id}"
            )

        typer.echo("  0    Skip this movie\n")

        while True:
            raw = typer.prompt(f"Selection [1-{len(results)}, 0=skip]")
            try:
                choice = int(raw)
                if choice == 0:
                    return SelectionResult(
                        selected=None,
                        mode=SelectionMode.INTERACTIVE,
                        skipped=True,
                    )
                if 1 <= choice <= len(results):
                    return SelectionResult(
                        selected=results[choice - 1],
                        mode=SelectionMode.INTERACTIVE,
                        was_manual=True,
                    )
            except ValueError:
                pass
