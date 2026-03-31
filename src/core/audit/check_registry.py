# src/core/audit/check_registry.py
from __future__ import annotations

from pathlib import Path
from typing import Optional

from core.audit.check import BaseCheck
from core.audit.checks.audio_checks import MissingDeAudioCheck, UnlabeledAudioCheck
from core.audit.checks.file_quality_checks import (
    BrokenFileCheck,
    InefficientCodecCheck,
    LowBitrateCheck,
    SuspiciousFileSizeCheck,
    WrongContainerCheck,
)
from core.audit.checks.naming_checks import (
    BadMovieNamingCheck,
    DuplicateMovieCheck,
    EmptyFolderCheck,
    FileInRootCheck,
    NameTooLongCheck,
    SpecialCharsCheck,
)
from core.audit.checks.series_checks import BadEpisodeNamingCheck, EpisodeGapCheck
from core.audit.checks.subtitle_checks import (
    MissingDeSubtitleCheck,
    MissingEnSubtitleCheck,
    NoSubtitlesAtAllCheck,
)


def _build_defaults(root_dir: Optional[Path] = None) -> list[BaseCheck]:
    checks: list[BaseCheck] = [
        MissingDeSubtitleCheck(),
        MissingEnSubtitleCheck(),
        NoSubtitlesAtAllCheck(),
        UnlabeledAudioCheck(),
        MissingDeAudioCheck(),
        EpisodeGapCheck(),
        BadEpisodeNamingCheck(),
        BrokenFileCheck(),
        WrongContainerCheck(),
        InefficientCodecCheck(),
        SuspiciousFileSizeCheck(),
        LowBitrateCheck(),
        BadMovieNamingCheck(),
        DuplicateMovieCheck(),
        SpecialCharsCheck(),
        NameTooLongCheck(),
    ]
    # Checks that need the root directory
    if root_dir is not None:
        checks.append(FileInRootCheck(root_dir))
        checks.append(EmptyFolderCheck(root_dir))
    return checks


class CheckRegistry:
    @staticmethod
    def all_checks(root_dir: Optional[Path] = None) -> list[BaseCheck]:
        """Return every registered check instance."""
        return _build_defaults(root_dir)

    @staticmethod
    def default_checks(root_dir: Optional[Path] = None) -> list[BaseCheck]:
        """Return the default set of checks (all checks)."""
        return _build_defaults(root_dir)

    @staticmethod
    def get_checks(
        ids: Optional[list[str]] = None,
        root_dir: Optional[Path] = None,
    ) -> list[BaseCheck]:
        """Return checks filtered by their check_id.  ``None`` returns all."""
        all_c = _build_defaults(root_dir)
        if ids is None:
            return all_c
        id_set = {i.strip().upper() for i in ids}
        return [c for c in all_c if c.check_id.upper() in id_set]
