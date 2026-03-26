"""
src/core/video/upscale_profiles.py

Named upscale profiles for the DVD → H.265 pipeline.

Profiles are applied before explicit CLI overrides, following the precedence:
  CLI values > profile values > built-in defaults

Built-in profiles
-----------------
dvd        Standard DVD upscale that mirrors DVD_h265_720p_improvment.ps1.
           720p · CRF 21 · preset medium · full filter chain.

dvd-hq     High-quality DVD rip for important films.
           720p · CRF 18 · preset slow · stronger sharpen.

dvd-fast   Fast batch processing for large NAS ingest queues.
           720p · CRF 23 · preset fast · lighter filter chain.

1080p      Upscale to Full HD for cinema-quality content.
           1080p · CRF 20 · preset medium · full filter chain.

anime      Optimised for animated content.
           720p · CRF 19 · preset slow · cropdetect disabled · gentle sharpen.

archive    Maximum-quality archival encode. Slow but smallest visible artefacts.
           720p · CRF 14 · preset veryslow · full filter chain.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from .upscaler import UpscaleOptions


@dataclass(frozen=True)
class UpscaleProfile:
    """A named configuration preset for the DVD upscale pipeline."""

    name: str
    description: str
    options: UpscaleOptions


# ---------------------------------------------------------------------------
# Built-in profiles
# ---------------------------------------------------------------------------

BUILTIN_PROFILES: dict[str, UpscaleProfile] = {
    # --- Standard / default ------------------------------------------------
    "dvd": UpscaleProfile(
        name="dvd",
        description=(
            "Standard DVD upscale (mirrors DVD_h265_720p_improvment.ps1). "
            "720p · CRF 21 · preset medium · full filter chain."
        ),
        options=UpscaleOptions(
            target_height=720,
            target_width=1280,
            crf=21,
            preset="medium",
            codec="libx265",
            gradfun_strength=4.0,
            eq_contrast=1.02,
            eq_brightness=0.0,
            eq_saturation=1.02,
            unsharp_luma=0.25,
            crop_skip_seconds=5,
            crop_sample_seconds=10,
            force_disable_crop=False,
        ),
    ),

    # --- High quality -------------------------------------------------------
    "dvd-hq": UpscaleProfile(
        name="dvd-hq",
        description=(
            "High-quality DVD rip for important films. "
            "720p · CRF 18 · preset slow · stronger sharpen."
        ),
        options=UpscaleOptions(
            target_height=720,
            target_width=1280,
            crf=18,
            preset="slow",
            codec="libx265",
            gradfun_strength=4.0,
            eq_contrast=1.02,
            eq_brightness=0.0,
            eq_saturation=1.02,
            unsharp_luma=0.30,
            crop_skip_seconds=5,
            crop_sample_seconds=15,
            force_disable_crop=False,
        ),
    ),

    # --- Fast / batch -------------------------------------------------------
    "dvd-fast": UpscaleProfile(
        name="dvd-fast",
        description=(
            "Fast batch processing for large NAS ingest queues. "
            "720p · CRF 23 · preset fast · lighter filter chain."
        ),
        options=UpscaleOptions(
            target_height=720,
            target_width=1280,
            crf=23,
            preset="fast",
            codec="libx265",
            gradfun_strength=2.0,
            eq_contrast=1.01,
            eq_brightness=0.0,
            eq_saturation=1.01,
            unsharp_luma=0.10,
            crop_skip_seconds=3,
            crop_sample_seconds=7,
            force_disable_crop=False,
        ),
    ),

    # --- Full HD ------------------------------------------------------------
    "1080p": UpscaleProfile(
        name="1080p",
        description=(
            "Upscale to Full HD for cinema-quality content. "
            "1080p · CRF 20 · preset medium · full filter chain."
        ),
        options=UpscaleOptions(
            target_height=1080,
            target_width=1920,
            crf=20,
            preset="medium",
            codec="libx265",
            gradfun_strength=4.0,
            eq_contrast=1.02,
            eq_brightness=0.0,
            eq_saturation=1.02,
            unsharp_luma=0.25,
            crop_skip_seconds=5,
            crop_sample_seconds=10,
            force_disable_crop=False,
        ),
    ),

    # --- Anime --------------------------------------------------------------
    "anime": UpscaleProfile(
        name="anime",
        description=(
            "Optimised for animated content. "
            "720p · CRF 19 · preset slow · cropdetect disabled · gentle sharpen."
        ),
        options=UpscaleOptions(
            target_height=720,
            target_width=1280,
            crf=19,
            preset="slow",
            codec="libx265",
            gradfun_strength=3.0,
            eq_contrast=1.01,
            eq_brightness=0.0,
            eq_saturation=1.03,
            unsharp_luma=0.15,
            crop_skip_seconds=5,
            crop_sample_seconds=10,
            force_disable_crop=True,
        ),
    ),

    # --- Archive ------------------------------------------------------------
    "archive": UpscaleProfile(
        name="archive",
        description=(
            "Maximum-quality archival encode. Slow but smallest visible artefacts. "
            "720p · CRF 14 · preset veryslow · full filter chain."
        ),
        options=UpscaleOptions(
            target_height=720,
            target_width=1280,
            crf=14,
            preset="veryslow",
            codec="libx265",
            gradfun_strength=4.0,
            eq_contrast=1.02,
            eq_brightness=0.0,
            eq_saturation=1.02,
            unsharp_luma=0.25,
            crop_skip_seconds=5,
            crop_sample_seconds=20,
            force_disable_crop=False,
        ),
    ),
}


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


def get_profile(name: str) -> UpscaleProfile:
    """Return the named profile.

    Args:
        name: Profile name (case-sensitive).

    Raises:
        ValueError: If *name* is not a known profile.
    """
    if name not in BUILTIN_PROFILES:
        known = ", ".join(sorted(BUILTIN_PROFILES))
        raise ValueError(
            f"Unknown upscale profile {name!r}. "
            f"Available profiles: {known}"
        )
    return BUILTIN_PROFILES[name]


def resolve_upscale_options(
    profile_name: str = "dvd",
    *,
    crf: int | None = None,
    encoder_preset: str | None = None,
    target_height: int | None = None,
    overwrite: bool = False,
) -> UpscaleOptions:
    """Build final :class:`UpscaleOptions` by applying CLI overrides on top of a
    named profile.

    Precedence (highest to lowest):
      *CLI explicit value* > *profile value* > *built-in default*

    Args:
        profile_name:    Name of the built-in profile (default ``"dvd"``).
        crf:             Override the profile's H.265 CRF value.
        encoder_preset:  Override the profile's ffmpeg encoding preset
                         (e.g. ``"fast"``, ``"slow"``).
        target_height:   Override the profile's output height in pixels.
        overwrite:       Allow overwriting existing output files.

    Returns:
        Fully resolved :class:`UpscaleOptions`.
    """
    profile = get_profile(profile_name)
    base = profile.options

    return replace(
        base,
        crf=crf if crf is not None else base.crf,
        preset=encoder_preset if encoder_preset is not None else base.preset,
        target_height=target_height if target_height is not None else base.target_height,
        overwrite=overwrite,
    )
