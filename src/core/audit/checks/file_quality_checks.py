# src/core/audit/checks/file_quality_checks.py
from __future__ import annotations

from pathlib import Path
from typing import Any

from core.audit.check import BaseCheck
from core.audit.models import AuditFinding, CheckSeverity, FindingKind

_VIDEO_CODECS_EFFICIENT = {"hevc", "h265", "av1", "vp9"}
_MIN_FILE_SIZE_BYTES = 100 * 1024 * 1024  # 100 MB
_LARGE_FILE_BYTES = 4 * 1024 * 1024 * 1024  # 4 GB
_MIN_VIDEO_BITRATE = 500_000  # 500 kbps


class BrokenFileCheck(BaseCheck):
    check_id = "B01"
    check_name = "Defekte Dateien"

    def run(
        self, files: list[Path], probes: dict[Path, dict[str, Any]]
    ) -> list[AuditFinding]:
        findings = []
        for f in files:
            probe = probes.get(f)
            if probe is None or f.stat().st_size == 0:
                findings.append(
                    AuditFinding(
                        kind=FindingKind.BROKEN_FILE,
                        severity=CheckSeverity.CRITICAL,
                        path=f,
                        message=(
                            "Datei ist leer oder konnte nicht analysiert werden "
                            "(ffprobe fehlgeschlagen)."
                        ),
                    )
                )
        return findings


class WrongContainerCheck(BaseCheck):
    check_id = "B02"
    check_name = "Falsches Container-Format (nicht MKV)"

    def run(
        self, files: list[Path], probes: dict[Path, dict[str, Any]]
    ) -> list[AuditFinding]:
        findings = []
        for f in files:
            if f.suffix.lower() in (".mp4", ".avi", ".mov", ".wmv"):
                findings.append(
                    AuditFinding(
                        kind=FindingKind.WRONG_CONTAINER,
                        severity=CheckSeverity.MEDIUM,
                        path=f,
                        message=(
                            f"Container {f.suffix.upper()} statt MKV. "
                            "Mehrere Spuren können nicht eingebettet werden."
                        ),
                        suggested_command=(
                            f'media-tool video convert "{f}" --language de'
                        ),
                    )
                )
        return findings


class InefficientCodecCheck(BaseCheck):
    check_id = "B03"
    check_name = "Nicht-H.265 bei großer Datei (> 4 GB)"

    def run(
        self, files: list[Path], probes: dict[Path, dict[str, Any]]
    ) -> list[AuditFinding]:
        findings = []
        for f in files:
            probe = probes.get(f, {})
            video_stream = next(
                (s for s in probe.get("streams", []) if s.get("codec_type") == "video"),
                None,
            )
            if not video_stream:
                continue
            codec = str(video_stream.get("codec_name", "")).lower()
            file_size = f.stat().st_size

            if codec not in _VIDEO_CODECS_EFFICIENT and file_size > _LARGE_FILE_BYTES:
                size_gb = file_size / 1_073_741_824
                findings.append(
                    AuditFinding(
                        kind=FindingKind.INEFFICIENT_CODEC,
                        severity=CheckSeverity.LOW,
                        path=f,
                        message=(
                            f"Codec {codec.upper()}, Größe {size_gb:.1f} GB. "
                            "H.265-Enkodierung würde Platz sparen."
                        ),
                        details={"codec": codec, "size_gb": round(size_gb, 2)},
                        suggested_command=(
                            f'media-tool video upscale "{f}" --profile dvd-hq'
                        ),
                    )
                )
        return findings


class SuspiciousFileSizeCheck(BaseCheck):
    check_id = "B04"
    check_name = "Verdächtig kleine Dateien (< 100 MB)"

    def run(
        self, files: list[Path], probes: dict[Path, dict[str, Any]]
    ) -> list[AuditFinding]:
        findings = []
        for f in files:
            size = f.stat().st_size
            if 0 < size < _MIN_FILE_SIZE_BYTES:
                size_mb = size / (1024 * 1024)
                findings.append(
                    AuditFinding(
                        kind=FindingKind.SUSPICIOUS_SIZE,
                        severity=CheckSeverity.MEDIUM,
                        path=f,
                        message=f"Datei nur {size_mb:.1f} MB — möglicherweise unvollständig.",
                        details={"size_mb": round(size_mb, 1)},
                    )
                )
        return findings


class LowBitrateCheck(BaseCheck):
    check_id = "B05"
    check_name = "Sehr niedrige Video-Bitrate"

    def run(
        self, files: list[Path], probes: dict[Path, dict[str, Any]]
    ) -> list[AuditFinding]:
        findings = []
        for f in files:
            probe = probes.get(f, {})
            video_stream = next(
                (s for s in probe.get("streams", []) if s.get("codec_type") == "video"),
                None,
            )
            if not video_stream:
                continue
            bitrate = int(video_stream.get("bit_rate") or 0)
            if 0 < bitrate < _MIN_VIDEO_BITRATE:
                findings.append(
                    AuditFinding(
                        kind=FindingKind.LOW_BITRATE,
                        severity=CheckSeverity.LOW,
                        path=f,
                        message=(
                            f"Video-Bitrate nur {bitrate // 1000} kbps "
                            "— sehr schlechte Qualität."
                        ),
                        details={"bitrate_kbps": bitrate // 1000},
                    )
                )
        return findings
