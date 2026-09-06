from __future__ import annotations

import csv
import json
from collections.abc import Mapping
from pathlib import Path

from core.audio.genre_normalizer import GenreNormalizationStatus, GenreNormalizer


def _create_config(
    tmp_path: Path, genres_payload: Mapping[str, object], aliases_payload: Mapping[str, str]
) -> tuple[Path, Path]:
    genres_path = tmp_path / "genres.json"
    aliases_path = tmp_path / "genre_aliases.json"
    genres_path.write_text(json.dumps(genres_payload, indent=2), encoding="utf-8")
    aliases_path.write_text(json.dumps(aliases_payload, indent=2), encoding="utf-8")
    return genres_path, aliases_path


def test_normalize_path_dry_run_applies_aliases_and_parents(tmp_path: Path) -> None:
    genres_payload = {
        "genres": ["Rock", "Alternative Rock", "Funk", "Hip-Hop", "Soul"],
        "parents": {"Alternative Rock": ["Rock"]},
    }
    aliases_payload = {
        "alternativ rock": "Alternative Rock",
        "hip hop": "Hip-Hop",
    }
    genres_path, aliases_path = _create_config(tmp_path, genres_payload, aliases_payload)

    file_one = tmp_path / "song1.mp3"
    file_two = tmp_path / "song2.flac"
    file_one.touch()
    file_two.touch()

    tags = {
        file_one: "alternativ rock",
        file_two: "Funk/Hip Hop/Soul",
    }
    writes: list[tuple[Path, str]] = []

    normalizer = GenreNormalizer(
        taxonomy_path=genres_path,
        aliases_path=aliases_path,
        genre_reader=lambda candidate: tags.get(candidate),
        genre_writer=lambda candidate, value: writes.append((candidate, value)),
    )

    run_result = normalizer.normalize_path(tmp_path, apply=False, reports_dir=tmp_path / "reports")

    assert len(run_result.results) == 2
    assert all(item.status == GenreNormalizationStatus.UPDATED for item in run_result.results)
    assert writes == []

    by_name = {item.path.name: item for item in run_result.results}
    assert by_name["song1.mp3"].normalized_genre == "Rock; Alternative Rock"
    assert by_name["song2.flac"].normalized_genre == "Funk; Hip-Hop; Soul"

    with run_result.reports.changes_csv.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 2

    with run_result.reports.genre_statistics_csv.open("r", encoding="utf-8", newline="") as handle:
        stats_rows = list(csv.DictReader(handle))
    counts = {row["genre"]: int(row["count"]) for row in stats_rows}
    assert counts["Rock"] == 1
    assert counts["Alternative Rock"] == 1
    assert counts["Funk"] == 1
    assert counts["Hip-Hop"] == 1
    assert counts["Soul"] == 1


def test_unknown_values_are_preserved_and_reported(tmp_path: Path) -> None:
    genres_payload = {
        "genres": ["Electronic", "House", "Deep House"],
        "parents": {
            "House": ["Electronic"],
            "Deep House": ["House"],
        },
    }
    genres_path, aliases_path = _create_config(tmp_path, genres_payload, {})

    target = tmp_path / "track.m4a"
    target.touch()
    tags = {target: "Deep House; WeirdGenre"}

    normalizer = GenreNormalizer(
        taxonomy_path=genres_path,
        aliases_path=aliases_path,
        genre_reader=lambda candidate: tags.get(candidate),
        genre_writer=lambda _candidate, _value: None,
    )

    run_result = normalizer.normalize_path(target, apply=False, reports_dir=tmp_path / "reports")

    assert len(run_result.results) == 1
    result = run_result.results[0]
    assert result.status == GenreNormalizationStatus.UPDATED
    assert result.normalized_genre == "Electronic; House; Deep House; WeirdGenre"
    assert result.unknown_genres == ("WeirdGenre",)

    with run_result.reports.unknown_genres_csv.open("r", encoding="utf-8", newline="") as handle:
        unknown_rows = list(csv.DictReader(handle))

    assert len(unknown_rows) == 1
    assert unknown_rows[0]["found_value"] == "WeirdGenre"
    assert unknown_rows[0]["count"] == "1"
    assert unknown_rows[0]["sample_file"].endswith("track.m4a")


def test_apply_mode_writes_tag_only_when_value_changes(tmp_path: Path) -> None:
    genres_payload = {
        "genres": ["Rock", "Alternative Rock"],
        "parents": {"Alternative Rock": ["Rock"]},
    }
    aliases_payload = {"alt rock": "Alternative Rock"}
    genres_path, aliases_path = _create_config(tmp_path, genres_payload, aliases_payload)

    changed = tmp_path / "changed.mp3"
    unchanged = tmp_path / "unchanged.mp3"
    changed.touch()
    unchanged.touch()

    tags = {
        changed: "alt rock",
        unchanged: "Rock; Alternative Rock",
    }
    writes: list[tuple[Path, str]] = []

    normalizer = GenreNormalizer(
        taxonomy_path=genres_path,
        aliases_path=aliases_path,
        genre_reader=lambda candidate: tags.get(candidate),
        genre_writer=lambda candidate, value: writes.append((candidate, value)),
    )

    run_result = normalizer.normalize_path(tmp_path, apply=True, reports_dir=tmp_path / "reports")
    by_name = {item.path.name: item for item in run_result.results}

    assert by_name["changed.mp3"].status == GenreNormalizationStatus.UPDATED
    assert by_name["changed.mp3"].applied is True
    assert by_name["unchanged.mp3"].status == GenreNormalizationStatus.SKIPPED

    assert writes == [(changed, "Rock; Alternative Rock")]


def test_german_rap_aliases_handle_typos_and_language_variants(tmp_path: Path) -> None:
    genres_payload = {
        "genres": ["Hip-Hop", "German Rap"],
        "parents": {"German Rap": ["Hip-Hop"]},
    }
    aliases_payload = {
        "deustchrap": "German Rap",
        "deutsch rap": "German Rap",
        "rap allemand": "German Rap",
    }
    genres_path, aliases_path = _create_config(tmp_path, genres_payload, aliases_payload)

    typo_file = tmp_path / "typo.mp3"
    spaced_file = tmp_path / "spaced.mp3"
    french_file = tmp_path / "french.mp3"
    typo_file.touch()
    spaced_file.touch()
    french_file.touch()

    tags = {
        typo_file: "Deustchrap",
        spaced_file: "Deutsch Rap",
        french_file: "Rap Allemand",
    }

    normalizer = GenreNormalizer(
        taxonomy_path=genres_path,
        aliases_path=aliases_path,
        genre_reader=lambda candidate: tags.get(candidate),
        genre_writer=lambda _candidate, _value: None,
    )

    run_result = normalizer.normalize_path(tmp_path, apply=False, reports_dir=tmp_path / "reports")
    by_name = {item.path.name: item for item in run_result.results}

    assert by_name["typo.mp3"].normalized_genre == "Hip-Hop; German Rap"
    assert by_name["spaced.mp3"].normalized_genre == "Hip-Hop; German Rap"
    assert by_name["french.mp3"].normalized_genre == "Hip-Hop; German Rap"


def test_rock_n_roll_aliases_map_to_rock_subgenre(tmp_path: Path) -> None:
    genres_payload = {
        "genres": ["Rock", "Rock 'n' Roll"],
        "parents": {"Rock 'n' Roll": ["Rock"]},
    }
    aliases_payload = {
        "rock and roll": "Rock 'n' Roll",
        "rock ’n’ roll": "Rock 'n' Roll",
        "rock'n'roll": "Rock 'n' Roll",
    }
    genres_path, aliases_path = _create_config(tmp_path, genres_payload, aliases_payload)

    spelled_file = tmp_path / "spelled.mp3"
    fancy_file = tmp_path / "fancy.mp3"
    compact_file = tmp_path / "compact.mp3"
    spelled_file.touch()
    fancy_file.touch()
    compact_file.touch()

    tags = {
        spelled_file: "Rock and Roll",
        fancy_file: "Rock ’n’ Roll",
        compact_file: "Rock'n'Roll",
    }

    normalizer = GenreNormalizer(
        taxonomy_path=genres_path,
        aliases_path=aliases_path,
        genre_reader=lambda candidate: tags.get(candidate),
        genre_writer=lambda _candidate, _value: None,
    )

    run_result = normalizer.normalize_path(tmp_path, apply=False, reports_dir=tmp_path / "reports")
    by_name = {item.path.name: item for item in run_result.results}

    assert by_name["spelled.mp3"].normalized_genre == "Rock; Rock 'n' Roll"
    assert by_name["fancy.mp3"].normalized_genre == "Rock; Rock 'n' Roll"
    assert by_name["compact.mp3"].normalized_genre == "Rock; Rock 'n' Roll"
