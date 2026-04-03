# src/core/audit/reporter.py
from __future__ import annotations

import csv
import json
from pathlib import Path

from core.audit.models import AuditReport, CheckSeverity, FindingKind

_SEVERITY_ICONS = {
    CheckSeverity.CRITICAL: "🔴",
    CheckSeverity.HIGH: "❌",
    CheckSeverity.MEDIUM: "⚠️ ",
    CheckSeverity.LOW: "ℹ️ ",
    CheckSeverity.INFO: "   ",
}

_KIND_LABELS: dict[FindingKind, str] = {
    FindingKind.MISSING_DE_SUBTITLE: "Filme ohne DE-Untertitel",
    FindingKind.MISSING_EN_SUBTITLE: "Filme ohne EN-Untertitel",
    FindingKind.NO_SUBTITLES: "Dateien ohne Untertitel",
    FindingKind.UNLABELED_AUDIO: "Audiospuren ohne Sprachkennzeichnung",
    FindingKind.MISSING_DE_AUDIO: "Kein deutsches Audio",
    FindingKind.EPISODE_GAP: "Fehlende Episoden (Lücken)",
    FindingKind.BAD_EPISODE_NAMING: "Falsch benannte Episoden",
    FindingKind.BROKEN_FILE: "Defekte Dateien",
    FindingKind.WRONG_CONTAINER: "Falsches Container-Format",
    FindingKind.INEFFICIENT_CODEC: "Uneffizienter Video-Codec",
    FindingKind.SUSPICIOUS_SIZE: "Verdächtig kleine Dateien",
    FindingKind.LOW_BITRATE: "Sehr niedrige Bitrate",
    FindingKind.NONSTANDARD_RESOLUTION: "Nicht-Standard-Auflösung",
    FindingKind.BAD_MOVIE_NAMING: "Falsch benannte Filme",
    FindingKind.DUPLICATE_MOVIE: "Doppelte Filme",
    FindingKind.FILE_IN_ROOT: "Dateien im Wurzelordner",
    FindingKind.EMPTY_FOLDER: "Leere Ordner",
    FindingKind.SPECIAL_CHARS: "Sonderzeichen im Dateinamen",
    FindingKind.NAME_TOO_LONG: "Name zu lang",
}


class AuditReporter:
    """Rendert AuditReport in verschiedene Ausgabeformate."""

    # ── Console ─────────────────────────────────────────────────────────

    @staticmethod
    def render_summary(report: AuditReport) -> str:
        lines = [
            f"\n── Audit-Report: {report.root_dir} ──────────────────────",
            f"   Dateien geprüft: {report.total_files}  |  Dauer: {report.duration_seconds:.1f}s",
            "",
        ]

        if not report.all_findings:
            lines.append("✅  Keine Probleme gefunden.")
            return "\n".join(lines)

        by_kind = report.by_kind
        for kind, findings in sorted(by_kind.items(), key=lambda x: x[1][0].severity.value):
            icon = _SEVERITY_ICONS.get(findings[0].severity, "?")
            label = _KIND_LABELS.get(kind, kind.value)
            lines.append(f"  {icon}  {len(findings):>4}×  {label}")

        lines += [
            "",
            f"   Gesamt: {len(report.all_findings)} Findings  "
            f"(🔴 {report.critical_count} kritisch  ❌ {report.high_count} hoch)",
            "─" * 60,
        ]
        return "\n".join(lines)

    @staticmethod
    def render_details(report: AuditReport, max_per_kind: int = 10) -> str:
        lines = [AuditReporter.render_summary(report), ""]
        by_kind = report.by_kind
        for kind, findings in by_kind.items():
            label = _KIND_LABELS.get(kind, kind.value)
            lines.append(f"\n── {label} ({len(findings)}) ──")
            for f in findings[:max_per_kind]:
                icon = _SEVERITY_ICONS.get(f.severity, "?")
                lines.append(f"  {icon}  {f.path.name}")
                lines.append(f"       {f.message}")
                if f.suggested_command:
                    lines.append(f"       → {f.suggested_command}")
            if len(findings) > max_per_kind:
                lines.append(f"  … und {len(findings) - max_per_kind} weitere (--export für vollständige Liste)")
        return "\n".join(lines)

    # ── CSV ─────────────────────────────────────────────────────────────

    @staticmethod
    def export_csv(report: AuditReport, output_path: Path) -> None:
        with open(output_path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(
                fh,
                fieldnames=[
                    "severity",
                    "check_id",
                    "kind",
                    "path",
                    "message",
                    "suggested_command",
                ],
            )
            writer.writeheader()
            for check_result in report.check_results:
                for finding in check_result.findings:
                    writer.writerow(
                        {
                            "severity": finding.severity.name,
                            "check_id": check_result.check_id,
                            "kind": finding.kind.value,
                            "path": str(finding.path),
                            "message": finding.message,
                            "suggested_command": finding.suggested_command or "",
                        }
                    )

    # ── JSON ─────────────────────────────────────────────────────────────

    @staticmethod
    def export_json(report: AuditReport, output_path: Path) -> None:
        data = {
            "root_dir": str(report.root_dir),
            "total_files": report.total_files,
            "duration_seconds": report.duration_seconds,
            "summary": {kind.value: len(findings) for kind, findings in report.by_kind.items()},
            "findings": [
                {
                    "severity": f.severity.name,
                    "kind": f.kind.value,
                    "path": str(f.path),
                    "message": f.message,
                    "details": f.details,
                    "suggested_command": f.suggested_command,
                }
                for f in report.all_findings
            ],
        }
        output_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
