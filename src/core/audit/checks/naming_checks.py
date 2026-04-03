# src/core/audit/checks/naming_checks.py
from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from core.audit.check import BaseCheck
from core.audit.models import AuditFinding, CheckSeverity, FindingKind

# Jellyfin-konformes Muster: "Titel (Jahr)" oder "Titel (Jahr) - Zusatz"
_MOVIE_NAMING_RE = re.compile(r".+\(\d{4}\)")
_TITLE_YEAR_RE = re.compile(r"^(.+?)\s*\((\d{4})\)")
_SPECIAL_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_MAX_NAME_LEN = 200
_SEASON_RE = re.compile(r"[Ss]eason", re.IGNORECASE)


class BadMovieNamingCheck(BaseCheck):
    check_id = "C01"
    check_name = "Falsche Filmbenennung (kein 'Titel (Jahr)')"

    def run(self, files: list[Path], probes: dict[Path, dict[str, Any]]) -> list[AuditFinding]:
        findings = []
        for f in files:
            is_series = any(_SEASON_RE.search(p.name) for p in f.parents)
            if is_series:
                continue
            if not _MOVIE_NAMING_RE.search(f.stem):
                findings.append(
                    AuditFinding(
                        kind=FindingKind.BAD_MOVIE_NAMING,
                        severity=CheckSeverity.HIGH,
                        path=f,
                        message=(f"'{f.name}' entspricht nicht dem Jellyfin-Schema 'Titel (Jahr).mkv'."),
                    )
                )
        return findings


class DuplicateMovieCheck(BaseCheck):
    check_id = "C02"
    check_name = "Doppelte Filme"

    def run(self, files: list[Path], probes: dict[Path, dict[str, Any]]) -> list[AuditFinding]:
        title_map: dict[str, list[Path]] = defaultdict(list)
        for f in files:
            m = _TITLE_YEAR_RE.search(f.stem)
            if m:
                title = re.sub(r"\W+", " ", m.group(1).lower()).strip()
                key = f"{title}_{m.group(2)}"
            else:
                key = re.sub(r"\W+", " ", f.stem.lower()).strip()
            title_map[key].append(f)

        findings = []
        for title, dupes in title_map.items():
            if len(dupes) > 1:
                for f in dupes:
                    findings.append(
                        AuditFinding(
                            kind=FindingKind.DUPLICATE_MOVIE,
                            severity=CheckSeverity.MEDIUM,
                            path=f,
                            message=(
                                f"'{title}' existiert {len(dupes)}× im Verzeichnis. Pfade: {[str(d) for d in dupes]}"
                            ),
                            details={"duplicate_paths": [str(d) for d in dupes]},
                        )
                    )
        return findings


class FileInRootCheck(BaseCheck):
    check_id = "C03"
    check_name = "Dateien direkt im Wurzelordner"

    def __init__(self, root_dir: Path) -> None:
        self._root = root_dir

    def run(self, files: list[Path], probes: dict[Path, dict[str, Any]]) -> list[AuditFinding]:
        findings = []
        for f in files:
            if f.parent == self._root:
                findings.append(
                    AuditFinding(
                        kind=FindingKind.FILE_IN_ROOT,
                        severity=CheckSeverity.MEDIUM,
                        path=f,
                        message=(f"'{f.name}' liegt direkt im Wurzelordner statt in eigenem Unterordner."),
                    )
                )
        return findings


class EmptyFolderCheck(BaseCheck):
    check_id = "C04"
    check_name = "Leere Ordner"

    def __init__(self, root_dir: Path) -> None:
        self._root = root_dir

    def run(self, files: list[Path], probes: dict[Path, dict[str, Any]]) -> list[AuditFinding]:
        findings = []
        for folder in self._root.rglob("*"):
            if folder.is_dir() and not any(folder.iterdir()):
                findings.append(
                    AuditFinding(
                        kind=FindingKind.EMPTY_FOLDER,
                        severity=CheckSeverity.LOW,
                        path=folder,
                        message=f"Leerer Ordner: '{folder}'.",
                    )
                )
        return findings


class SpecialCharsCheck(BaseCheck):
    check_id = "C05"
    check_name = "Jellyfin-inkompatible Sonderzeichen im Dateinamen"

    def run(self, files: list[Path], probes: dict[Path, dict[str, Any]]) -> list[AuditFinding]:
        findings = []
        for f in files:
            bad_chars = _SPECIAL_CHARS.findall(f.name)
            if bad_chars:
                findings.append(
                    AuditFinding(
                        kind=FindingKind.SPECIAL_CHARS,
                        severity=CheckSeverity.MEDIUM,
                        path=f,
                        message=(f"Problematische Zeichen: {set(bad_chars)} in '{f.name}'."),
                    )
                )
        return findings


class NameTooLongCheck(BaseCheck):
    check_id = "C06"
    check_name = "Dateiname zu lang (> 200 Zeichen)"

    def run(self, files: list[Path], probes: dict[Path, dict[str, Any]]) -> list[AuditFinding]:
        findings = []
        for f in files:
            if len(f.name) > _MAX_NAME_LEN:
                findings.append(
                    AuditFinding(
                        kind=FindingKind.NAME_TOO_LONG,
                        severity=CheckSeverity.LOW,
                        path=f,
                        message=(f"Dateiname ist {len(f.name)} Zeichen lang (Limit: {_MAX_NAME_LEN})."),
                        details={"name_length": len(f.name)},
                    )
                )
        return findings
