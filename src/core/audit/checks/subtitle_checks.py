# src/core/audit/checks/subtitle_checks.py
from __future__ import annotations

from pathlib import Path
from typing import Any

from core.audit.check import BaseCheck
from core.audit.models import AuditFinding, CheckSeverity, FindingKind

_DE_CODES = {"ger", "deu", "de", "german"}
_EN_CODES = {"eng", "en", "english"}


def _subtitle_langs(probe: dict[str, Any]) -> set[str]:
    return {
        (s.get("tags") or {}).get("language", "").lower()
        for s in probe.get("streams", [])
        if s.get("codec_type") == "subtitle"
    }


class MissingDeSubtitleCheck(BaseCheck):
    check_id = "A01"
    check_name = "Fehlende deutsche Untertitel"

    def run(self, files: list[Path], probes: dict[Path, dict[str, Any]]) -> list[AuditFinding]:
        findings = []
        for f in files:
            langs = _subtitle_langs(probes.get(f, {}))
            if not langs.intersection(_DE_CODES):
                findings.append(
                    AuditFinding(
                        kind=FindingKind.MISSING_DE_SUBTITLE,
                        severity=CheckSeverity.HIGH,
                        path=f,
                        message=(f"Keine deutsche Untertitelspur. Vorhandene: {langs or 'keine'}"),
                        suggested_command=(f'media-tool subtitle download "{f}" --languages de'),
                    )
                )
        return findings


class MissingEnSubtitleCheck(BaseCheck):
    check_id = "A02"
    check_name = "Fehlende englische Untertitel"

    def run(self, files: list[Path], probes: dict[Path, dict[str, Any]]) -> list[AuditFinding]:
        findings = []
        for f in files:
            langs = _subtitle_langs(probes.get(f, {}))
            if not langs.intersection(_EN_CODES):
                findings.append(
                    AuditFinding(
                        kind=FindingKind.MISSING_EN_SUBTITLE,
                        severity=CheckSeverity.MEDIUM,
                        path=f,
                        message=(f"Keine englische Untertitelspur. Vorhandene: {langs or 'keine'}"),
                        suggested_command=(f'media-tool subtitle download "{f}" --languages en'),
                    )
                )
        return findings


class NoSubtitlesAtAllCheck(BaseCheck):
    check_id = "A03"
    check_name = "Keine Untertitel vorhanden"

    def run(self, files: list[Path], probes: dict[Path, dict[str, Any]]) -> list[AuditFinding]:
        findings = []
        for f in files:
            subs = [s for s in probes.get(f, {}).get("streams", []) if s.get("codec_type") == "subtitle"]
            if not subs:
                findings.append(
                    AuditFinding(
                        kind=FindingKind.NO_SUBTITLES,
                        severity=CheckSeverity.MEDIUM,
                        path=f,
                        message="Datei enthält überhaupt keine Untertitelspur.",
                        suggested_command=f'media-tool subtitle download "{f}"',
                    )
                )
        return findings
