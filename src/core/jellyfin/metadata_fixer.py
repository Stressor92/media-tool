# src/core/jellyfin/metadata_fixer.py
from __future__ import annotations

import logging

from core.jellyfin.client import JellyfinClient
from core.jellyfin.library_manager import LibraryManager
from core.jellyfin.models import (
    FixResult,
    ItemType,
    JellyfinItem,
    MetadataIssue,
    MetadataIssueKind,
)

logger = logging.getLogger(__name__)


class MetadataFixer:
    """
    Fixes automatically resolvable metadata problems.

    Strategy:
    - AUTO-FIXABLE issues → Jellyfin refresh with forced metadata download
    - WRONG_SERIES_MATCH  → interactive confirmation recommended
    - DUPLICATES          → report only, never auto-delete
    """

    def __init__(self, manager: LibraryManager, client: JellyfinClient) -> None:
        self._manager = manager
        self._client = client

    def fix_issue(self, issue: MetadataIssue) -> FixResult:
        """Attempts to fix a single issue."""
        if not issue.auto_fixable:
            return FixResult(
                issue=issue,
                success=False,
                error="Not automatically fixable — manual action required.",
            )

        match issue.kind:
            case (
                MetadataIssueKind.MISSING_OVERVIEW
                | MetadataIssueKind.MISSING_POSTER
                | MetadataIssueKind.MISSING_BACKDROP
                | MetadataIssueKind.MISSING_YEAR
            ):
                return self._force_metadata_refresh(issue)

            case MetadataIssueKind.UNMATCHED:
                return self._fix_unmatched(issue)

            case MetadataIssueKind.MISSING_EPISODE_NUM:
                return self._fix_episode_number(issue)

            case _:
                return FixResult(
                    issue=issue,
                    success=False,
                    error=f"No handler for {issue.kind}",
                )

    def fix_all_auto(self, issues: list[MetadataIssue]) -> list[FixResult]:
        """Fixes all automatically resolvable issues."""
        auto_fixable = [i for i in issues if i.auto_fixable]
        logger.info(
            "%d of %d issues are automatically fixable.",
            len(auto_fixable),
            len(issues),
        )
        return [self.fix_issue(issue) for issue in auto_fixable]

    # ── Fix strategies ───────────────────────────────────────────────────

    def _force_metadata_refresh(self, issue: MetadataIssue) -> FixResult:
        """Forces a full metadata refresh for an item."""
        result = self._manager.refresh_item(issue.item.id, replace_metadata=True)
        if result.triggered:
            logger.info("Forced refresh for: %s", issue.item.name)
            return FixResult(
                issue=issue,
                success=True,
                applied_fix=f"Full metadata refresh for '{issue.item.name}'.",
            )
        return FixResult(issue=issue, success=False, error=result.error)

    def _fix_unmatched(self, issue: MetadataIssue) -> FixResult:
        """Triggers refresh; if provider IDs are still missing, manual identification is needed."""
        result = self._manager.refresh_item(issue.item.id, replace_metadata=True)
        return FixResult(
            issue=issue,
            success=result.triggered,
            applied_fix="Refresh triggered — provider IDs will be searched again.",
            error=result.error,
        )

    def _fix_episode_number(self, issue: MetadataIssue) -> FixResult:
        """Writes episode number from file path into Jellyfin metadata via a full refresh."""
        if not issue.suggested_fix:
            return FixResult(
                issue=issue,
                success=False,
                error="Episode number could not be read from path.",
            )
        result = self._manager.refresh_item(issue.item.id, replace_metadata=True)
        return FixResult(
            issue=issue,
            success=result.triggered,
            applied_fix=f"Refresh triggered. Detected pattern: {issue.suggested_fix}",
        )

    def reassign_series(
        self,
        episode_id: str,
        correct_series_id: str,
    ) -> FixResult:
        """
        Reassigns a mismatched episode to the correct series.
        This is a guided fix: it triggers a refresh of the target series and
        returns instructions.
        """
        episode = self._manager.get_item(episode_id)
        series = self._manager.get_item(correct_series_id)
        if not episode or not series:
            # Return a minimal error result without a real item
            item = episode or series or JellyfinItem(
                id="", name="unknown", item_type=ItemType.UNKNOWN
            )
            return FixResult(
                issue=MetadataIssue(
                    item=item,
                    kind=MetadataIssueKind.WRONG_SERIES_MATCH,
                    description="Item not found.",
                ),
                success=False,
                error="Episode or target series not found.",
            )

        self._manager.refresh_item(correct_series_id)

        return FixResult(
            issue=MetadataIssue(
                item=episode,
                kind=MetadataIssueKind.WRONG_SERIES_MATCH,
                description="Reassigned.",
            ),
            success=True,
            applied_fix=(
                f"Refresh triggered for series '{series.name}'. "
                f"Episode '{episode.name}' should be reassigned."
            ),
        )
