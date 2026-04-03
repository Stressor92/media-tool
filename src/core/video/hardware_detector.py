"""
src/core/video/hardware_detector.py

Detects available hardware encoders (NVENC, AMF, QSV) via ffmpeg.

Two-stage detection:
  1. Check ffmpeg -encoders for codec availability
  2. Run probe encode to validate actual hardware accessibility
"""

from __future__ import annotations

import functools
import logging
import subprocess
import time
from typing import Literal

from core.video.models import EncoderType, HardwareCapabilities

logger = logging.getLogger(__name__)


class HardwareDetector:
    """Detects and manages available hardware encoders."""

    # Priority order for encoder selection
    ENCODER_PRIORITY: list[tuple[str, str, EncoderType]] = [
        ("hevc_nvenc", "NVENC", EncoderType.NVENC),
        ("hevc_amf", "AMF", EncoderType.AMF),
        ("hevc_qsv", "QSV", EncoderType.QSV),
    ]

    SW_ENCODER = ("libx265", "Software", EncoderType.SOFTWARE)

    @staticmethod
    def _check_encoder_in_ffmpeg(encoder_name: str) -> bool:
        """
        Check if an encoder is listed in ffmpeg -encoders.

        Args:
            encoder_name: Encoder codec name (e.g., "hevc_nvenc")

        Returns:
            True if encoder is in ffmpeg's encoder list.
        """
        try:
            result = subprocess.run(
                ["ffmpeg", "-hide_banner", "-encoders"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return encoder_name in result.stdout
        except Exception as e:
            logger.debug(f"Failed to check ffmpeg encoders: {e}")
            return False

    @staticmethod
    def _probe_encoder(encoder_name: str, timeout_sec: int = 10) -> bool:
        """
        Validate that an encoder actually works via a minimal test encode.

        Runs a 1-frame null encode to ensure the encoder and its hardware
        are accessible, not just present in ffmpeg.

        Args:
            encoder_name: Encoder codec name to test
            timeout_sec: Test timeout in seconds

        Returns:
            True if the encoder test succeeds.
        """
        probe_cmd = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            "nullsrc=s=64x64:d=0.1",
            "-c:v",
            encoder_name,
            "-f",
            "null",
            "-",
        ]

        try:
            result = subprocess.run(probe_cmd, capture_output=True, timeout=timeout_sec)
            return result.returncode == 0
        except subprocess.TimeoutExpired:
            logger.debug(f"Encoder probe timeout for {encoder_name}")
            return False
        except Exception as e:
            logger.debug(f"Encoder probe failed for {encoder_name}: {e}")
            return False

    @staticmethod
    @functools.lru_cache(maxsize=1)
    def detect(force: bool = False, probe_timeout_sec: int = 10) -> HardwareCapabilities:
        """
        Detect available hardware encoders.

        Results are cached for the program lifetime unless force=True.

        Args:
            force: Force re-detection even if cached (cache is bypassed)
            probe_timeout_sec: Timeout for encoder probe tests

        Returns:
            HardwareCapabilities with detection results.
        """
        start_time = time.time()
        probe_errors: dict[str, str] = {}
        available: dict[EncoderType, bool] = {
            EncoderType.NVENC: False,
            EncoderType.AMF: False,
            EncoderType.QSV: False,
        }

        # Stage 1: Check encoder list
        encoders_found: dict[str, EncoderType] = {}
        for codec_name, _, encoder_type in HardwareDetector.ENCODER_PRIORITY:
            if HardwareDetector._check_encoder_in_ffmpeg(codec_name):
                encoders_found[codec_name] = encoder_type

        # Stage 2: Probe available encoders
        for codec_name, friendly_name, encoder_type in HardwareDetector.ENCODER_PRIORITY:
            if codec_name not in encoders_found:
                logger.debug(f"{friendly_name} ({codec_name}) not found in ffmpeg")
                continue

            if HardwareDetector._probe_encoder(codec_name, timeout_sec=probe_timeout_sec):
                available[encoder_type] = True
                logger.debug(f"{friendly_name} ({codec_name}) probe succeeded")
            else:
                probe_errors[codec_name] = "Encoder probe failed (hardware unavailable?)"
                logger.debug(f"{friendly_name} ({codec_name}) probe failed")

        # Determine best available encoder
        best_encoder_codec = HardwareDetector.SW_ENCODER[0]  # default: libx265
        best_encoder_type = EncoderType.SOFTWARE

        for codec_name, _friendly_name, encoder_type in HardwareDetector.ENCODER_PRIORITY:
            if available.get(encoder_type, False):
                best_encoder_codec = codec_name
                best_encoder_type = encoder_type
                break

        elapsed_ms = (time.time() - start_time) * 1000

        caps = HardwareCapabilities(
            best_encoder=best_encoder_codec,
            encoder_type=best_encoder_type,
            nvenc_available=available[EncoderType.NVENC],
            amf_available=available[EncoderType.AMF],
            qsv_available=available[EncoderType.QSV],
            detection_time_ms=elapsed_ms,
            probe_errors=probe_errors,
        )

        logger.info(
            "Hardware detection complete (%.1fms): NVENC=%s AMF=%s QSV=%s → using %s",
            elapsed_ms,
            "available" if caps.nvenc_available else "not_found",
            "available" if caps.amf_available else "not_found",
            "available" if caps.qsv_available else "not_found",
            best_encoder_type.value,
        )

        return caps

    @staticmethod
    def clear_cache() -> None:
        """Clear the detection cache (useful for testing or --force-detect)."""
        HardwareDetector.detect.cache_clear()

    @staticmethod
    def get_best_encoder(
        preferred: str | Literal["auto"] = "auto",
        force_software: bool = False,
    ) -> tuple[str, EncoderType]:
        """
        Get the best encoder to use based on preferences and availability.

        Args:
            preferred: "auto", "nvenc", "amf", "qsv", or "software"
            force_software: If True, always return software encoder

        Returns:
            Tuple of (codec_name, EncoderType)
        """
        if force_software:
            return HardwareDetector.SW_ENCODER[0], EncoderType.SOFTWARE

        caps = HardwareDetector.detect()

        if preferred == "auto" or preferred == "":
            return caps.best_encoder, caps.encoder_type

        # Map preference names to codec names
        preference_map: dict[str, str] = {
            "nvenc": "hevc_nvenc",
            "amf": "hevc_amf",
            "qsv": "hevc_qsv",
            "software": "libx265",
        }

        pref_codec = preference_map.get(preferred.lower(), "")
        if not pref_codec:
            logger.warning(f"Unknown encoder preference '{preferred}', using auto")
            return caps.best_encoder, caps.encoder_type

        # Check if preferred encoder is available
        if pref_codec == "hevc_nvenc" and caps.nvenc_available:
            return pref_codec, EncoderType.NVENC
        elif pref_codec == "hevc_amf" and caps.amf_available:
            return pref_codec, EncoderType.AMF
        elif pref_codec == "hevc_qsv" and caps.qsv_available:
            return pref_codec, EncoderType.QSV
        elif pref_codec == "libx265":
            return pref_codec, EncoderType.SOFTWARE
        else:
            logger.warning(f"Preferred encoder '{preferred}' not available, using {caps.encoder_type.value}")
            return caps.best_encoder, caps.encoder_type
