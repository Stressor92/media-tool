# src/core/audit/checks/audio_checks.py
from __future__ import annotations

from pathlib import Path
from typing import Any

from core.audit.check import BaseCheck
from core.audit.models import AuditFinding, CheckSeverity, FindingKind

_DE_CODES = {"ger", "deu", "de"}
_EN_CODES = {"eng", "en"}
_UNDEFINED = {"und", "", "unknown"}


class UnlabeledAudioCheck(BaseCheck):
    check_id = "A04"
    check_name = "Audiospuren ohne Sprachmetadaten"

    def run(self, files: list[Path], probes: dict[Path, dict[str, Any]]) -> list[AuditFinding]:
        findings = []
        for f in files:
            audio_streams = [s for s in probes.get(f, {}).get("streams", []) if s.get("codec_type") == "audio"]
            unlabeled = [s for s in audio_streams if (s.get("tags") or {}).get("language", "und").lower() in _UNDEFINED]
            if unlabeled:
                findings.append(
                    AuditFinding(
                        kind=FindingKind.UNLABELED_AUDIO,
                        severity=CheckSeverity.HIGH,
                        path=f,
                        message=(f"{len(unlabeled)} von {len(audio_streams)} " "Audiospuren ohne Sprachkennzeichnung."),
                        details={"unlabeled_count": len(unlabeled)},
                        suggested_command=(f'media-tool audio tag "{f}" --detect-language'),
                    )
                )
        return findings


class MissingDeAudioCheck(BaseCheck):
    check_id = "A05"
    check_name = "Nur englische Audio, keine deutsche Spur"

    def run(self, files: list[Path], probes: dict[Path, dict[str, Any]]) -> list[AuditFinding]:
        findings = []
        for f in files:
            audio_streams = [s for s in probes.get(f, {}).get("streams", []) if s.get("codec_type") == "audio"]
            langs = {(s.get("tags") or {}).get("language", "").lower() for s in audio_streams}
            has_en = bool(langs.intersection(_EN_CODES))
            has_de = bool(langs.intersection(_DE_CODES))

            if has_en and not has_de and audio_streams:
                findings.append(
                    AuditFinding(
                        kind=FindingKind.MISSING_DE_AUDIO,
                        severity=CheckSeverity.MEDIUM,
                        path=f,
                        message="Nur englische Audiospur — keine deutsche Version vorhanden.",
                    )
                )
        return findings
