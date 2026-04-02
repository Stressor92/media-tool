from __future__ import annotations

from collections import defaultdict
from pathlib import Path
import logging
from typing import Protocol

from core.ebook.models import BookIdentity, DuplicateGroup
from core.ebook.deduplication.version_comparator import VersionComparator
from utils.fuzzy_matcher import FuzzyMatcher

logger = logging.getLogger(__name__)


class SupportsBookIdentifier(Protocol):
    def identify(self, file_path: Path) -> BookIdentity: ...


class SupportsIsbnExtractor(Protocol):
    def extract(self, file_path: Path) -> str | None: ...


class DuplicateFinder:
    """Find duplicate ebook groups by ISBN and fuzzy title/author matching."""

    def __init__(
        self,
        isbn_extractor: SupportsIsbnExtractor,
        book_identifier: SupportsBookIdentifier,
        version_comparator: VersionComparator,
        fuzzy_matcher: FuzzyMatcher,
    ) -> None:
        self.isbn_extractor = isbn_extractor
        self.identifier = book_identifier
        self.comparator = version_comparator
        self.fuzzy_matcher = fuzzy_matcher

    def find_duplicates(self, library_path: Path, recursive: bool = True) -> list[DuplicateGroup]:
        ebooks = self._scan_ebooks(library_path, recursive=recursive)
        identities: dict[Path, BookIdentity] = {path: self.identifier.identify(path) for path in ebooks}

        isbn_groups = self._group_by_isbn(identities)
        title_groups = self._group_by_title_author(identities, isbn_groups)

        candidate_groups = [*isbn_groups.values(), *title_groups.values()]
        duplicate_groups = [group for group in candidate_groups if len(group) > 1]

        results: list[DuplicateGroup] = []
        for group in duplicate_groups:
            best_version = self.comparator.select_best(group)
            confidence = self._group_confidence(group, identities)
            results.append(
                DuplicateGroup(
                    books=group,
                    match_confidence=confidence,
                    best_version=best_version,
                    reason=self._explain_selection(best_version),
                )
            )

        logger.info("Duplicate scan complete", extra={"groups": len(results), "files": len(ebooks)})
        return results

    def _scan_ebooks(self, root_path: Path, recursive: bool) -> list[Path]:
        if not root_path.exists():
            return []
        extensions = {".epub", ".mobi", ".azw3", ".pdf", ".azw"}
        pattern = "**/*" if recursive else "*"
        return [path for path in root_path.glob(pattern) if path.is_file() and path.suffix.lower() in extensions]

    def _group_by_isbn(self, identities: dict[Path, BookIdentity]) -> dict[str, list[Path]]:
        groups: dict[str, list[Path]] = defaultdict(list)
        for path, identity in identities.items():
            isbn = identity.isbn13 or identity.isbn
            if isbn:
                groups[isbn].append(path)
        return dict(groups)

    def _group_by_title_author(
        self,
        identities: dict[Path, BookIdentity],
        isbn_groups: dict[str, list[Path]],
    ) -> dict[str, list[Path]]:
        grouped_paths = {path for paths in isbn_groups.values() for path in paths}
        remaining = {path: identity for path, identity in identities.items() if path not in grouped_paths}

        groups: dict[str, list[Path]] = defaultdict(list)
        consumed: set[Path] = set()

        for path1, identity1 in remaining.items():
            if path1 in consumed:
                continue

            key = f"{identity1.title}||{identity1.author}"
            groups[key].append(path1)
            consumed.add(path1)

            for path2, identity2 in remaining.items():
                if path2 in consumed:
                    continue

                title_sim = self.fuzzy_matcher.similarity(identity1.title, identity2.title)
                author_sim = self.fuzzy_matcher.similarity(identity1.author, identity2.author)
                if title_sim >= 0.88 and author_sim >= 0.88:
                    groups[key].append(path2)
                    consumed.add(path2)

        return dict(groups)

    def _group_confidence(self, group: list[Path], identities: dict[Path, BookIdentity]) -> float:
        isbns = {identities[path].isbn13 or identities[path].isbn for path in group}
        has_isbn_match = len(isbns) == 1 and None not in isbns
        return 0.98 if has_isbn_match else 0.9

    @staticmethod
    def _explain_selection(best_version: Path) -> str:
        suffix = best_version.suffix.lower()
        if suffix == ".epub":
            return "EPUB selected for broad compatibility and reflow quality"
        if suffix == ".azw3":
            return "AZW3 selected for high Kindle compatibility"
        if suffix == ".mobi":
            return "MOBI selected as the best available Kindle-compatible format"
        return "PDF selected because no higher-priority format was available"
