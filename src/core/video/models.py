"""
src/core/video/models.py

Data models for hardware detection and encoder management.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class EncoderType(StrEnum):
    """Available hardware encoder types."""

    NVENC = "nvenc"
    AMF = "amf"
    QSV = "qsv"
    SOFTWARE = "software"


@dataclass
class HardwareCapabilities:
    """Detected hardware encoder capabilities."""

    best_encoder: str  # e.g., "hevc_nvenc"
    encoder_type: EncoderType  # NVENC | AMF | QSV | SOFTWARE
    nvenc_available: bool = False
    amf_available: bool = False
    qsv_available: bool = False
    detection_time_ms: float = 0.0
    probe_errors: dict[str, str] = field(default_factory=dict)  # encoder → error message

    @property
    def has_hardware_acceleration(self) -> bool:
        """Return True if any hardware encoder is available."""
        return self.encoder_type != EncoderType.SOFTWARE
