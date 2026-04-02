# src/core/audit/checks/series_checks.py
from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from core.audit.check import BaseCheck
from core.audit.models import AuditFinding, CheckSeverity, FindingKind

_EPISODE_RE = re.compile(r"[Ss](\d{1,2})[Ee](\d{1,2})")
_SEASON_DIR = re.compile(r"[Ss]eason\s*(\d+)", re.IGNORECASE)


class EpisodeGapCheck(BaseCheck):
    """Erkennt Lücken in Staffeln (z. B. S01E01, S01E02, S01E04 → E03 fehlt)."""

    check_id = "A06"
    check_name = "Fehlende Episoden (Lücken in Staffeln)"

    def run(self, files: list[Path], probes: dict[Path, dict[str, Any]]) -> list[AuditFinding]:
        # Dateien nach Serie/Staffel gruppieren
        series_map: dict[str, dict[int, list[int]]] = defaultdict(lambda: defaultdict(list))

        for f in files:
            m = _EPISODE_RE.search(f.name)
            if not m:
                continue
            season = int(m.group(1))
            episode = int(m.group(2))
            series_name = f.parents[1].name if len(f.parents) >= 2 else f.parent.name
            series_map[series_name][season].append(episode)

        findings = []
        for series_name, seasons in series_map.items():
            for season, episodes in seasons.items():
                sorted_eps = sorted(set(episodes))
                if not sorted_eps:
                    continue
                expected = list(range(sorted_eps[0], sorted_eps[-1] + 1))
                missing = [e for e in expected if e not in sorted_eps]
                if missing:
                    series_path = next(
                        (f.parents[1] for f in files if len(f.parents) >= 2 and f.parents[1].name == series_name),
                        Path(series_name),
                    )
                    findings.append(
                        AuditFinding(
                            kind=FindingKind.EPISODE_GAP,
                            severity=CheckSeverity.HIGH,
                            path=series_path,
                            message=(
                                f"'{series_name}' Staffel {season:02d}: "
                                f"Episode(n) {missing} fehlen. "
                                f"Vorhanden: {sorted_eps}"
                            ),
                            details={
                                "series": series_name,
                                "season": season,
                                "missing_episodes": missing,
                            },
                        )
                    )
        return findings


class BadEpisodeNamingCheck(BaseCheck):
    """Episodendateien ohne S##E##-Muster."""

    check_id = "A07"
    check_name = "Episoden ohne S##E##-Benennung"

    def run(self, files: list[Path], probes: dict[Path, dict[str, Any]]) -> list[AuditFinding]:
        findings = []
        for f in files:
            is_in_series = any(_SEASON_DIR.search(p.name) for p in f.parents)
            if is_in_series and not _EPISODE_RE.search(f.name):
                findings.append(
                    AuditFinding(
                        kind=FindingKind.BAD_EPISODE_NAMING,
                        severity=CheckSeverity.HIGH,
                        path=f,
                        message=(f"Datei liegt in Serien-Ordner, " f"enthält aber kein S##E##-Muster: '{f.name}'"),
                    )
                )
        return findings
