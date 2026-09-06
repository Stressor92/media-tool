"""Genre normalization with taxonomy-aware parent expansion and reporting."""

from __future__ import annotations

import csv
import json
import logging
import re
from collections import Counter
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import Enum, auto
from importlib import import_module
from pathlib import Path
from typing import Any, cast

logger = logging.getLogger(__name__)

GenreReader = Callable[[Path], str | None]
GenreWriter = Callable[[Path, str], None]


class GenreNormalizationStatus(Enum):
    """Result status for per-file genre normalization."""

    UPDATED = auto()
    SKIPPED = auto()
    FAILED = auto()


@dataclass(frozen=True)
class GenreNormalizationFileResult:
    """Outcome for one audio file genre normalization attempt."""

    path: Path
    status: GenreNormalizationStatus
    original_genre: str | None = None
    normalized_genre: str | None = None
    canonical_genres: tuple[str, ...] = ()
    unknown_genres: tuple[str, ...] = ()
    applied: bool = False
    message: str | None = None


@dataclass(frozen=True)
class GenreReportPaths:
    """Absolute report file locations for a normalization run."""

    changes_csv: Path
    unknown_genres_csv: Path
    genre_statistics_csv: Path


@dataclass(frozen=True)
class GenreNormalizationRun:
    """Summary of one normalization run over a path."""

    results: list[GenreNormalizationFileResult]
    reports: GenreReportPaths


@dataclass(frozen=True)
class GenreTaxonomy:
    """Canonical genres and explicit parent relations."""

    genres: tuple[str, ...]
    parents: dict[str, tuple[str, ...]]


class GenreNormalizer:
    """Normalize genre tags based on explicit taxonomy and aliases."""

    SUPPORTED_EXTENSIONS = frozenset({".mp3", ".flac", ".m4a", ".ogg"})

    def __init__(
        self,
        taxonomy_path: Path | None = None,
        aliases_path: Path | None = None,
        genre_reader: GenreReader | None = None,
        genre_writer: GenreWriter | None = None,
    ) -> None:
        self._taxonomy_path = taxonomy_path or self.default_taxonomy_path()
        self._aliases_path = aliases_path or self.default_aliases_path()

        self._taxonomy = self._load_taxonomy(self._taxonomy_path)
        self._aliases = self._load_aliases(self._aliases_path, self._taxonomy)
        self._genre_reader = genre_reader or self._read_genre_from_tag
        self._genre_writer = genre_writer or self._write_genre_to_tag

        self._canonical_by_key = {self._genre_key(name): name for name in self._taxonomy.genres}
        self._expanded_cache: dict[str, tuple[str, ...]] = {}

    @staticmethod
    def _repo_root() -> Path:
        return Path(__file__).resolve().parents[3]

    @classmethod
    def default_taxonomy_path(cls) -> Path:
        return cls._repo_root() / "config" / "genres.json"

    @classmethod
    def default_aliases_path(cls) -> Path:
        return cls._repo_root() / "config" / "genre_aliases.json"

    def normalize_path(
        self,
        path: Path,
        *,
        apply: bool = False,
        recursive: bool = True,
        reports_dir: Path | None = None,
    ) -> GenreNormalizationRun:
        """Normalize all supported files in a file or directory path."""
        resolved_reports_dir = (reports_dir or Path("reports")).resolve()
        paths = self._collect_target_files(path, recursive=recursive)

        results = [self.normalize_file(item, apply=apply) for item in paths]
        report_paths = self._write_reports(results, resolved_reports_dir)

        return GenreNormalizationRun(results=results, reports=report_paths)

    def normalize_file(self, file_path: Path, *, apply: bool = False) -> GenreNormalizationFileResult:
        """Normalize one file and optionally write the resulting genre tag."""
        if not file_path.exists() or not file_path.is_file():
            return GenreNormalizationFileResult(
                path=file_path,
                status=GenreNormalizationStatus.FAILED,
                message="Datei nicht gefunden.",
            )

        if file_path.suffix.lower() not in self.SUPPORTED_EXTENSIONS:
            return GenreNormalizationFileResult(
                path=file_path,
                status=GenreNormalizationStatus.SKIPPED,
                message="Format wird nicht unterstuetzt.",
            )

        try:
            raw_genre = self._genre_reader(file_path)
        except Exception as exc:
            logger.warning("Could not read genre tag from %s: %s", file_path, exc)
            return GenreNormalizationFileResult(
                path=file_path,
                status=GenreNormalizationStatus.FAILED,
                message=f"GENRE konnte nicht gelesen werden: {exc}",
            )

        if raw_genre is None or not raw_genre.strip():
            return GenreNormalizationFileResult(
                path=file_path,
                status=GenreNormalizationStatus.SKIPPED,
                message="Kein GENRE-Tag gefunden.",
            )

        normalized, canonical_values, unknown_values = self._normalize_genre_value(raw_genre)
        original = raw_genre.strip()

        if not normalized:
            return GenreNormalizationFileResult(
                path=file_path,
                status=GenreNormalizationStatus.SKIPPED,
                original_genre=original,
                normalized_genre=original,
                unknown_genres=unknown_values,
                message="GENRE enthaelt keine auswertbaren Werte.",
            )

        if normalized == original:
            return GenreNormalizationFileResult(
                path=file_path,
                status=GenreNormalizationStatus.SKIPPED,
                original_genre=original,
                normalized_genre=normalized,
                canonical_genres=canonical_values,
                unknown_genres=unknown_values,
                message="Bereits normalisiert.",
            )

        if apply:
            try:
                self._genre_writer(file_path, normalized)
            except Exception as exc:
                logger.warning("Could not write normalized genre to %s: %s", file_path, exc)
                return GenreNormalizationFileResult(
                    path=file_path,
                    status=GenreNormalizationStatus.FAILED,
                    original_genre=original,
                    normalized_genre=normalized,
                    canonical_genres=canonical_values,
                    unknown_genres=unknown_values,
                    message=f"GENRE konnte nicht geschrieben werden: {exc}",
                )

        return GenreNormalizationFileResult(
            path=file_path,
            status=GenreNormalizationStatus.UPDATED,
            original_genre=original,
            normalized_genre=normalized,
            canonical_genres=canonical_values,
            unknown_genres=unknown_values,
            applied=apply,
        )

    def _collect_target_files(self, path: Path, *, recursive: bool) -> list[Path]:
        if not path.exists():
            return [path]

        if path.is_file():
            return [path]

        if not path.is_dir():
            return [path]

        iterator = path.rglob("*") if recursive else path.glob("*")
        return sorted(
            (
                file_path
                for file_path in iterator
                if file_path.is_file() and file_path.suffix.lower() in self.SUPPORTED_EXTENSIONS
            ),
            key=lambda candidate: str(candidate).lower(),
        )

    def _normalize_genre_value(self, raw_value: str) -> tuple[str, tuple[str, ...], tuple[str, ...]]:
        tokens = self._split_genre_values(raw_value)

        canonical_order: list[str] = []
        unknown_order: list[str] = []
        canonical_seen: set[str] = set()
        unknown_seen: set[str] = set()

        for token in tokens:
            alias_target = self._aliases.get(self._genre_key(token), token)
            canonical = self._canonical_by_key.get(self._genre_key(alias_target))

            if canonical:
                for expanded in self._expand_with_parents(canonical):
                    expanded_key = self._genre_key(expanded)
                    if expanded_key in canonical_seen:
                        continue
                    canonical_seen.add(expanded_key)
                    canonical_order.append(expanded)
                continue

            unknown_key = self._genre_key(alias_target)
            if unknown_key and unknown_key not in unknown_seen and unknown_key not in canonical_seen:
                unknown_seen.add(unknown_key)
                unknown_order.append(alias_target.strip())

        merged = [*canonical_order, *unknown_order]
        return "; ".join(merged), tuple(canonical_order), tuple(unknown_order)

    @staticmethod
    def _split_genre_values(raw_value: str) -> list[str]:
        normalized = raw_value.strip()
        normalized = normalized.replace("\\", ";")
        normalized = normalized.replace("/", ";")
        normalized = normalized.replace(",", ";")
        normalized = re.sub(r"\s+&\s+", ";", normalized)
        normalized = re.sub(r"\s*;\s*", ";", normalized)
        normalized = re.sub(r";{2,}", ";", normalized)
        normalized = normalized.strip("; ")
        if not normalized:
            return []
        return [part.strip() for part in normalized.split(";") if part.strip()]

    def _expand_with_parents(self, genre: str) -> tuple[str, ...]:
        cached = self._expanded_cache.get(genre)
        if cached is not None:
            return cached

        expanded = self._expand_recursive(genre, lineage=())
        self._expanded_cache[genre] = expanded
        return expanded

    def _expand_recursive(self, genre: str, *, lineage: tuple[str, ...]) -> tuple[str, ...]:
        if genre in lineage:
            chain = " -> ".join([*lineage, genre])
            raise ValueError(f"Zyklische Genre-Hierarchie erkannt: {chain}")

        ordered: list[str] = []
        seen: set[str] = set()

        for parent in self._taxonomy.parents.get(genre, ()):  # roots have no explicit parent list
            for item in self._expand_recursive(parent, lineage=(*lineage, genre)):
                item_key = self._genre_key(item)
                if item_key in seen:
                    continue
                seen.add(item_key)
                ordered.append(item)

        genre_key = self._genre_key(genre)
        if genre_key not in seen:
            ordered.append(genre)

        return tuple(ordered)

    @staticmethod
    def _genre_key(value: str) -> str:
        normalized = value.strip().casefold().replace("_", " ")
        normalized = re.sub(r"\s+", " ", normalized)
        return normalized

    def _write_reports(self, results: list[GenreNormalizationFileResult], report_dir: Path) -> GenreReportPaths:
        report_dir.mkdir(parents=True, exist_ok=True)

        report_paths = GenreReportPaths(
            changes_csv=report_dir / "changes.csv",
            unknown_genres_csv=report_dir / "unknown_genres.csv",
            genre_statistics_csv=report_dir / "genre_statistics.csv",
        )

        self._write_changes_report(results, report_paths.changes_csv)
        self._write_unknown_report(results, report_paths.unknown_genres_csv)
        self._write_statistics_report(results, report_paths.genre_statistics_csv)

        return report_paths

    @staticmethod
    def _write_changes_report(results: list[GenreNormalizationFileResult], output_path: Path) -> None:
        rows = [
            result
            for result in results
            if result.status == GenreNormalizationStatus.UPDATED
            and result.original_genre is not None
            and result.normalized_genre is not None
        ]

        with output_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["file", "old_genre", "new_genre"])
            writer.writeheader()
            for item in rows:
                writer.writerow(
                    {
                        "file": str(item.path),
                        "old_genre": item.original_genre,
                        "new_genre": item.normalized_genre,
                    }
                )

    @staticmethod
    def _write_unknown_report(results: list[GenreNormalizationFileResult], output_path: Path) -> None:
        counts: Counter[str] = Counter()
        display_names: dict[str, str] = {}
        samples: dict[str, str] = {}

        for result in results:
            for unknown in result.unknown_genres:
                key = GenreNormalizer._genre_key(unknown)
                counts[key] += 1
                display_names.setdefault(key, unknown)
                samples.setdefault(key, str(result.path))

        with output_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["found_value", "count", "sample_file"])
            writer.writeheader()
            for key, count in sorted(counts.items(), key=lambda item: (-item[1], item[0])):
                writer.writerow(
                    {
                        "found_value": display_names[key],
                        "count": count,
                        "sample_file": samples[key],
                    }
                )

    @staticmethod
    def _write_statistics_report(results: list[GenreNormalizationFileResult], output_path: Path) -> None:
        counts: Counter[str] = Counter()
        for result in results:
            for genre in result.canonical_genres:
                counts[genre] += 1

        with output_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["genre", "count"])
            writer.writeheader()
            for genre, count in sorted(counts.items(), key=lambda item: (-item[1], item[0])):
                writer.writerow({"genre": genre, "count": count})

    @staticmethod
    def _load_taxonomy(path: Path) -> GenreTaxonomy:
        if not path.exists():
            raise ValueError(f"Genres-Konfiguration fehlt: {path}")

        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Genres-Konfiguration ist kein gueltiges JSON: {exc}") from exc

        if not isinstance(payload, dict):
            raise ValueError("Genres-Konfiguration muss ein JSON-Objekt sein.")

        raw_genres = payload.get("genres")
        raw_parents = payload.get("parents", {})

        if not isinstance(raw_genres, list) or not all(isinstance(item, str) and item.strip() for item in raw_genres):
            raise ValueError("genres muss eine Liste aus nicht-leeren Strings sein.")

        if not isinstance(raw_parents, dict):
            raise ValueError("parents muss ein JSON-Objekt sein.")

        canonical_genres: list[str] = []
        seen_genres: set[str] = set()
        for genre in raw_genres:
            cleaned = genre.strip()
            key = GenreNormalizer._genre_key(cleaned)
            if key in seen_genres:
                raise ValueError(f"Doppeltes Genre in Taxonomie: {cleaned}")
            seen_genres.add(key)
            canonical_genres.append(cleaned)

        canonical_lookup = {GenreNormalizer._genre_key(item): item for item in canonical_genres}
        normalized_parents: dict[str, tuple[str, ...]] = {}

        for child_raw, parent_list_raw in raw_parents.items():
            if not isinstance(child_raw, str) or not child_raw.strip():
                raise ValueError("Ungueltiger Child-Key in parents.")
            if not isinstance(parent_list_raw, list) or not all(
                isinstance(parent, str) and parent.strip() for parent in parent_list_raw
            ):
                raise ValueError(f"parents[{child_raw}] muss eine Liste aus Strings sein.")

            child_key = GenreNormalizer._genre_key(child_raw)
            child = canonical_lookup.get(child_key)
            if child is None:
                raise ValueError(f"Child-Genre in parents ist nicht in genres definiert: {child_raw}")

            deduped_parents: list[str] = []
            parent_seen: set[str] = set()
            for parent_raw in parent_list_raw:
                parent_key = GenreNormalizer._genre_key(parent_raw)
                parent = canonical_lookup.get(parent_key)
                if parent is None:
                    raise ValueError(f"Parent-Genre '{parent_raw}' fuer '{child}' ist nicht in genres definiert.")
                if parent_key in parent_seen:
                    continue
                parent_seen.add(parent_key)
                deduped_parents.append(parent)

            normalized_parents[child] = tuple(deduped_parents)

        taxonomy = GenreTaxonomy(genres=tuple(canonical_genres), parents=normalized_parents)

        # Validate parent graph once to fail fast on cycles.
        normalizer = GenreNormalizer.__new__(GenreNormalizer)
        normalizer._taxonomy = taxonomy
        normalizer._expanded_cache = {}
        normalizer._canonical_by_key = {GenreNormalizer._genre_key(name): name for name in taxonomy.genres}
        for genre in taxonomy.genres:
            normalizer._expand_with_parents(genre)

        return taxonomy

    @staticmethod
    def _load_aliases(path: Path, taxonomy: GenreTaxonomy) -> dict[str, str]:
        if not path.exists():
            raise ValueError(f"Alias-Konfiguration fehlt: {path}")

        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Alias-Konfiguration ist kein gueltiges JSON: {exc}") from exc

        if not isinstance(payload, dict):
            raise ValueError("Alias-Konfiguration muss ein JSON-Objekt sein.")

        canonical_lookup = {GenreNormalizer._genre_key(item): item for item in taxonomy.genres}
        aliases: dict[str, str] = {}

        for raw_key, raw_target in payload.items():
            if not isinstance(raw_key, str) or not raw_key.strip():
                raise ValueError("Alias-Key muss ein nicht-leerer String sein.")
            if not isinstance(raw_target, str) or not raw_target.strip():
                raise ValueError(f"Alias-Ziel fuer '{raw_key}' muss ein nicht-leerer String sein.")

            alias_key = GenreNormalizer._genre_key(raw_key)
            target = canonical_lookup.get(GenreNormalizer._genre_key(raw_target))
            if target is None:
                raise ValueError(f"Alias-Ziel '{raw_target}' fuer '{raw_key}' ist nicht in genres definiert.")
            aliases[alias_key] = target

        return aliases

    @staticmethod
    def _read_genre_from_tag(file_path: Path) -> str | None:
        mutagen_module = import_module("mutagen")
        mutagen_file = cast(Callable[..., Any], mutagen_module.File)

        audio_easy = mutagen_file(file_path, easy=True)
        audio_raw = mutagen_file(file_path)
        if audio_easy is None and audio_raw is None:
            return None

        easy_value = GenreNormalizer._read_tag_value(audio_easy, keys=("genre",))
        if easy_value:
            return easy_value

        return GenreNormalizer._read_tag_value(audio_raw, keys=("TCON", "\u00a9gen", "GENRE", "genre"))

    @staticmethod
    def _write_genre_to_tag(file_path: Path, genre_value: str) -> None:
        mutagen_module = import_module("mutagen")
        mutagen_file = cast(Callable[..., Any], mutagen_module.File)

        audio = mutagen_file(file_path, easy=True)
        if audio is None:
            raise ValueError("Format wird von mutagen nicht unterstuetzt.")

        audio["genre"] = [genre_value]
        audio.save()

    @staticmethod
    def _read_tag_value(audio_object: Any, keys: tuple[str, ...]) -> str | None:
        mapping = GenreNormalizer._resolve_tag_mapping(audio_object)
        for key in keys:
            raw_value = GenreNormalizer._extract_mapping_value(mapping, key)
            normalized = GenreNormalizer._normalize_tag_value(raw_value)
            if normalized:
                return normalized
        return None

    @staticmethod
    def _resolve_tag_mapping(audio_object: Any) -> Mapping[str, Any] | None:
        if audio_object is None:
            return None

        if callable(getattr(audio_object, "get", None)):
            return cast(Mapping[str, Any], audio_object)

        tags = getattr(audio_object, "tags", None)
        if callable(getattr(tags, "get", None)):
            return cast(Mapping[str, Any], tags)

        return None

    @staticmethod
    def _extract_mapping_value(mapping: Mapping[str, Any] | None, key: str) -> Any:
        if mapping is None:
            return None
        getter = getattr(mapping, "get", None)
        if not callable(getter):
            return None
        return getter(key)

    @staticmethod
    def _normalize_tag_value(value: Any) -> str | None:
        if value is None:
            return None
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        if isinstance(value, list | tuple | set):
            parts = [GenreNormalizer._normalize_tag_value(item) for item in value]
            filtered = [item for item in parts if item]
            if not filtered:
                return None
            return "; ".join(filtered)

        text_value = getattr(value, "text", None)
        if text_value is not None:
            return GenreNormalizer._normalize_tag_value(text_value)

        coerced = str(value).strip()
        return coerced or None
