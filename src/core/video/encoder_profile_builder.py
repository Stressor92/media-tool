"""
src/core/video/encoder_profile_builder.py

Maps upscale profiles to encoder-specific ffmpeg parameters.

Each profile (dvd-fast, dvd-balanced, dvd-hq, etc.) is translated into
encoder-native parameters (NVENC preset, AMF quality, QSV preset, libx265 crf).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from core.video.models import EncoderType, HardwareCapabilities

logger = logging.getLogger(__name__)


@dataclass
class EncoderParams:
    """Encoder-specific rendering parameters."""

    encoder: str  # ffmpeg codec name (e.g., "hevc_nvenc")
    encoder_type: EncoderType
    base_args: list[str]  # ffmpeg arguments specific to this encoder
    profile_name: str  # source profile (e.g., "dvd-hq")


class EncoderProfileBuilder:
    """
    Maps upscale profiles and detected hardware into concrete ffmpeg encoder args.

    Profile precedence: profile settings → hardware detection → fallback to software

    Example:
        builder = EncoderProfileBuilder(
            profile="dvd-hq",
            hw_caps=HardwareDetector.detect(),
        )
        params = builder.build()
        # → EncoderParams with NVENC args, or AMF, or QSV, or libx265 as fallback
    """

    # Profile → encoder parameter mapping
    # Each profile defines the parameters for each encoder type

    PROFILE_PARAMS: dict[str, dict[EncoderType, dict[str, str | int]]] = {
        # dvd-fast: Speed-optimized (~4×realtime with GPU, ~1× with CPU)
        "dvd-fast": {
            EncoderType.NVENC: {
                "preset": "p3",  # 1=fastest, 7=slowest
                "cq": "26",  # quality (equivalent to CRF)
            },
            EncoderType.AMF: {
                "quality": "speed",  # speed | balanced | quality
                "qp_i": "28",
                "qp_p": "30",
            },
            EncoderType.QSV: {
                "preset": "veryfast",
                "global_quality": "26",
            },
            EncoderType.SOFTWARE: {
                "crf": "26",
                "preset": "medium",
            },
        },
        # dvd-balanced: Balanced quality/speed (~2.5× realtime with GPU, ~0.6× with CPU)
        "dvd-balanced": {
            EncoderType.NVENC: {
                "preset": "p5",
                "cq": "24",
            },
            EncoderType.AMF: {
                "quality": "balanced",
                "qp_i": "26",
                "qp_p": "28",
            },
            EncoderType.QSV: {
                "preset": "medium",
                "global_quality": "24",
            },
            EncoderType.SOFTWARE: {
                "crf": "24",
                "preset": "slow",
            },
        },
        # dvd-hq: High-quality (~1.5× realtime with GPU, ~0.3× with CPU)
        "dvd-hq": {
            EncoderType.NVENC: {
                "preset": "p7",  # slowest, best quality
                "cq": "22",
            },
            EncoderType.AMF: {
                "quality": "quality",
                "qp_i": "24",
                "qp_p": "26",
            },
            EncoderType.QSV: {
                "preset": "veryslow",
                "global_quality": "22",
            },
            EncoderType.SOFTWARE: {
                "crf": "22",
                "preset": "slow",
            },
        },
        # archive: Maximum quality, slow encode
        "archive": {
            EncoderType.NVENC: {
                "preset": "p7",
                "cq": "20",
            },
            EncoderType.AMF: {
                "quality": "quality",
                "qp_i": "22",
                "qp_p": "24",
            },
            EncoderType.QSV: {
                "preset": "veryslow",
                "global_quality": "20",
            },
            EncoderType.SOFTWARE: {
                "crf": "18",
                "preset": "veryslow",
            },
        },
        # anime: Optimized for animation (same as dvd-balanced, slight quality boost)
        "anime": {
            EncoderType.NVENC: {
                "preset": "p5",
                "cq": "23",
            },
            EncoderType.AMF: {
                "quality": "balanced",
                "qp_i": "25",
                "qp_p": "27",
            },
            EncoderType.QSV: {
                "preset": "medium",
                "global_quality": "23",
            },
            EncoderType.SOFTWARE: {
                "crf": "23",
                "preset": "slow",
            },
        },
        # jellyfin: Jellyfin-optimized (PAL 576p)
        "jellyfin": {
            EncoderType.NVENC: {
                "preset": "p5",
                "cq": "24",
            },
            EncoderType.AMF: {
                "quality": "balanced",
                "qp_i": "26",
                "qp_p": "28",
            },
            EncoderType.QSV: {
                "preset": "medium",
                "global_quality": "24",
            },
            EncoderType.SOFTWARE: {
                "crf": "24",
                "preset": "slow",
            },
        },
        # dvd (default)
        "dvd": {
            EncoderType.NVENC: {
                "preset": "p5",
                "cq": "24",
            },
            EncoderType.AMF: {
                "quality": "balanced",
                "qp_i": "26",
                "qp_p": "28",
            },
            EncoderType.QSV: {
                "preset": "medium",
                "global_quality": "24",
            },
            EncoderType.SOFTWARE: {
                "crf": "24",
                "preset": "medium",
            },
        },
        # 1080p
        "1080p": {
            EncoderType.NVENC: {
                "preset": "p5",
                "cq": "23",
            },
            EncoderType.AMF: {
                "quality": "balanced",
                "qp_i": "25",
                "qp_p": "27",
            },
            EncoderType.QSV: {
                "preset": "medium",
                "global_quality": "23",
            },
            EncoderType.SOFTWARE: {
                "crf": "23",
                "preset": "medium",
            },
        },
    }

    def __init__(
        self,
        profile: str = "dvd",
        hw_caps: HardwareCapabilities | None = None,
        force_software: bool = False,
        preferred_encoder: str | None = None,
    ):
        """
        Initialize the encoder profile builder.

        Args:
            profile: Profile name (e.g., "dvd-hq")
            hw_caps: Detected hardware capabilities (auto-detected if None)
            force_software: Force software encoding regardless of hardware
            preferred_encoder: Override hardware selection ("nvenc", "amf", "qsv", "software")
        """
        self.profile = profile
        self.force_software = force_software
        self.preferred_encoder = preferred_encoder

        if hw_caps is None:
            from core.video.hardware_detector import HardwareDetector

            hw_caps = HardwareDetector.detect()

        self.hw_caps = hw_caps

    def _get_encoder_type(self) -> EncoderType:
        """Determine which encoder type to use based on preferences and availability."""
        if self.force_software:
            return EncoderType.SOFTWARE

        if self.preferred_encoder:
            pref = self.preferred_encoder.lower()
            if pref == "nvenc" and self.hw_caps.nvenc_available:
                return EncoderType.NVENC
            elif pref == "amf" and self.hw_caps.amf_available:
                return EncoderType.AMF
            elif pref == "qsv" and self.hw_caps.qsv_available:
                return EncoderType.QSV
            elif pref == "software":
                return EncoderType.SOFTWARE
            else:
                logger.warning(
                    f"Preferred encoder '{self.preferred_encoder}' not available, using {self.hw_caps.encoder_type.value}"
                )

        # Use best available
        return self.hw_caps.encoder_type

    def build(self) -> EncoderParams:
        """
        Build encoder parameters for the configured profile and hardware.

        Returns:
            EncoderParams with ffmpeg-ready arguments.
        """
        encoder_type = self._get_encoder_type()
        profile_name = self.profile.lower()

        # Get profile parameters, fallback to "dvd" if unknown
        profile_params = self.PROFILE_PARAMS.get(profile_name)
        if profile_params is None:
            logger.warning(f"Profile '{profile_name}' not found, using 'dvd'")
            profile_params = self.PROFILE_PARAMS["dvd"]
            profile_name = "dvd"

        # Get encoder-specific params
        encoder_config = profile_params.get(encoder_type, profile_params[EncoderType.SOFTWARE])

        # Build encoder-specific arguments
        args = self._build_encoder_args(encoder_type, encoder_config)

        # Map encoder type to ffmpeg codec name
        codec_names = {
            EncoderType.NVENC: "hevc_nvenc",
            EncoderType.AMF: "hevc_amf",
            EncoderType.QSV: "hevc_qsv",
            EncoderType.SOFTWARE: "libx265",
        }

        logger.info(f"Using {encoder_type.value} for profile '{profile_name}'")

        return EncoderParams(
            encoder=codec_names[encoder_type],
            encoder_type=encoder_type,
            base_args=args,
            profile_name=profile_name,
        )

    @staticmethod
    def _build_encoder_args(encoder_type: EncoderType, config: dict[str, str | int]) -> list[str]:
        """
        Build ffmpeg arguments for the given encoder and config.

        Args:
            encoder_type: Type of encoder (NVENC, AMF, QSV, SOFTWARE)
            config: Encoder-specific parameters

        Returns:
            List of ffmpeg command-line arguments
        """
        args: list[str] = []

        if encoder_type == EncoderType.NVENC:
            args.extend(["-c:v", "hevc_nvenc"])
            args.extend(["-preset", str(config.get("preset", "p5"))])
            args.extend(["-rc", "vbr"])
            args.extend(["-cq", str(config.get("cq", "24"))])
            args.extend(["-b:v", "0"])
            args.extend(["-maxrate", "10M", "-bufsize", "20M"])
            args.extend(["-spatial_aq", "1", "-temporal_aq", "1"])
            args.extend(["-pix_fmt", "yuv420p"])

        elif encoder_type == EncoderType.AMF:
            args.extend(["-c:v", "hevc_amf"])
            args.extend(["-quality", str(config.get("quality", "balanced"))])
            args.extend(["-rc", "cqp"])
            args.extend(["-qp_i", str(config.get("qp_i", "26"))])
            args.extend(["-qp_p", str(config.get("qp_p", "28"))])
            args.extend(["-pix_fmt", "yuv420p"])

        elif encoder_type == EncoderType.QSV:
            args.extend(["-c:v", "hevc_qsv"])
            args.extend(["-preset", str(config.get("preset", "medium"))])
            args.extend(["-global_quality", str(config.get("global_quality", "24"))])
            args.extend(["-look_ahead", "1"])
            args.extend(["-pix_fmt", "nv12"])

        else:  # SOFTWARE
            args.extend(["-c:v", "libx265"])
            args.extend(["-crf", str(config.get("crf", "24"))])
            args.extend(["-preset", str(config.get("preset", "medium"))])
            args.extend(["-pix_fmt", "yuv420p"])

        return args
