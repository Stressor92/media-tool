"""
tests/unit/test_upscale_profiles.py

Unit tests for the upscale profile system.
"""

from __future__ import annotations

import pytest

from core.video.upscale_profiles import (
    BUILTIN_PROFILES,
    UpscaleProfile,
    get_profile,
    resolve_upscale_options,
)
from core.video.upscaler import UpscaleOptions


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

EXPECTED_PROFILES = {"dvd", "dvd-hq", "dvd-fast", "1080p", "anime", "archive", "jellyfin"}


# ---------------------------------------------------------------------------
# BUILTIN_PROFILES catalogue
# ---------------------------------------------------------------------------


def test_all_expected_profiles_present() -> None:
    assert EXPECTED_PROFILES == set(BUILTIN_PROFILES.keys())


def test_all_profiles_are_upscale_profile_instances() -> None:
    for name, profile in BUILTIN_PROFILES.items():
        assert isinstance(profile, UpscaleProfile), f"{name} is not an UpscaleProfile"


def test_all_profiles_have_upscale_options() -> None:
    for name, profile in BUILTIN_PROFILES.items():
        assert isinstance(profile.options, UpscaleOptions), (
            f"Profile {name!r} options is not UpscaleOptions"
        )


def test_all_profiles_have_non_empty_description() -> None:
    for name, profile in BUILTIN_PROFILES.items():
        assert profile.description.strip(), f"Profile {name!r} has empty description"


def test_all_profiles_name_matches_key() -> None:
    for key, profile in BUILTIN_PROFILES.items():
        assert profile.name == key, (
            f"Profile key {key!r} doesn't match profile.name {profile.name!r}"
        )


# ---------------------------------------------------------------------------
# Individual profile characteristics
# ---------------------------------------------------------------------------


class TestDvdProfile:
    def test_default_quality(self) -> None:
        p = BUILTIN_PROFILES["dvd"]
        assert p.options.crf == 21
        assert p.options.preset == "medium"
        assert p.options.target_height == 720

    def test_full_filter_chain(self) -> None:
        p = BUILTIN_PROFILES["dvd"]
        assert p.options.gradfun_strength == 4.0
        assert p.options.unsharp_luma == 0.15
        assert p.options.force_disable_crop is False

    def test_codec_is_libx265(self) -> None:
        assert BUILTIN_PROFILES["dvd"].options.codec == "libx265"


class TestDvdHqProfile:
    def test_lower_crf_than_dvd(self) -> None:
        hq = BUILTIN_PROFILES["dvd-hq"].options
        dvd = BUILTIN_PROFILES["dvd"].options
        assert hq.crf < dvd.crf

    def test_slower_preset(self) -> None:
        assert BUILTIN_PROFILES["dvd-hq"].options.preset == "slow"

    def test_stronger_sharpen(self) -> None:
        hq = BUILTIN_PROFILES["dvd-hq"].options
        dvd = BUILTIN_PROFILES["dvd"].options
        assert hq.unsharp_luma > dvd.unsharp_luma


class TestDvdFastProfile:
    def test_higher_crf_than_dvd(self) -> None:
        fast = BUILTIN_PROFILES["dvd-fast"].options
        dvd = BUILTIN_PROFILES["dvd"].options
        assert fast.crf > dvd.crf

    def test_fast_preset(self) -> None:
        assert BUILTIN_PROFILES["dvd-fast"].options.preset == "fast"

    def test_lighter_filter_chain(self) -> None:
        fast = BUILTIN_PROFILES["dvd-fast"].options
        dvd = BUILTIN_PROFILES["dvd"].options
        assert fast.gradfun_strength < dvd.gradfun_strength
        assert fast.unsharp_luma < dvd.unsharp_luma


class TestProfile1080p:
    def test_target_height(self) -> None:
        assert BUILTIN_PROFILES["1080p"].options.target_height == 1080

    def test_target_width(self) -> None:
        assert BUILTIN_PROFILES["1080p"].options.target_width == 1920

    def test_reasonable_crf(self) -> None:
        # Should be stricter (lower) than the standard dvd CRF
        assert BUILTIN_PROFILES["1080p"].options.crf < BUILTIN_PROFILES["dvd"].options.crf


class TestAnimeProfile:
    def test_force_disable_crop_is_true(self) -> None:
        assert BUILTIN_PROFILES["anime"].options.force_disable_crop is True

    def test_slow_preset_for_quality(self) -> None:
        assert BUILTIN_PROFILES["anime"].options.preset == "slow"

    def test_gentle_sharpen(self) -> None:
        # Anime profile should sharpen less than the standard dvd profile
        anime = BUILTIN_PROFILES["anime"].options
        dvd = BUILTIN_PROFILES["dvd"].options
        assert anime.unsharp_luma < dvd.unsharp_luma


class TestArchiveProfile:
    def test_lowest_crf(self) -> None:
        # archive must have the lowest (best quality) CRF of all profiles
        archive_crf = BUILTIN_PROFILES["archive"].options.crf
        for name, p in BUILTIN_PROFILES.items():
            if name != "archive":
                assert archive_crf <= p.options.crf, (
                    f"archive CRF ({archive_crf}) is not ≤ {name} CRF ({p.options.crf})"
                )

    def test_veryslow_preset(self) -> None:
        assert BUILTIN_PROFILES["archive"].options.preset == "veryslow"


# ---------------------------------------------------------------------------
# get_profile()
# ---------------------------------------------------------------------------


def test_get_profile_returns_correct_profile() -> None:
    profile = get_profile("dvd")
    assert profile.name == "dvd"


def test_get_profile_raises_for_unknown_name() -> None:
    with pytest.raises(ValueError, match="Unknown upscale profile"):
        get_profile("nonexistent-profile")


def test_get_profile_error_message_lists_known_profiles() -> None:
    with pytest.raises(ValueError, match="dvd"):
        get_profile("bogus")


# ---------------------------------------------------------------------------
# resolve_upscale_options() — precedence rules
# ---------------------------------------------------------------------------


def test_resolve_uses_profile_defaults_when_no_overrides() -> None:
    opts = resolve_upscale_options("dvd")
    assert opts.crf == BUILTIN_PROFILES["dvd"].options.crf
    assert opts.preset == BUILTIN_PROFILES["dvd"].options.preset
    assert opts.target_height == BUILTIN_PROFILES["dvd"].options.target_height


def test_resolve_crf_override_beats_profile() -> None:
    opts = resolve_upscale_options("dvd", crf=16)
    assert opts.crf == 16


def test_resolve_encoder_preset_override_beats_profile() -> None:
    opts = resolve_upscale_options("dvd", encoder_preset="ultrafast")
    assert opts.preset == "ultrafast"


def test_resolve_height_override_beats_profile() -> None:
    opts = resolve_upscale_options("dvd", target_height=480)
    assert opts.target_height == 480


def test_resolve_overwrite_is_passed_through() -> None:
    opts = resolve_upscale_options("dvd", overwrite=True)
    assert opts.overwrite is True


def test_resolve_none_override_does_not_change_profile_value() -> None:
    opts = resolve_upscale_options("dvd", crf=None)
    assert opts.crf == BUILTIN_PROFILES["dvd"].options.crf


def test_resolve_profile_preserves_filter_settings() -> None:
    """Non-overridable fields (gradfun, eq, unsharp) come intact from profile."""
    opts = resolve_upscale_options("dvd-fast", crf=20)
    assert opts.gradfun_strength == BUILTIN_PROFILES["dvd-fast"].options.gradfun_strength
    assert opts.unsharp_luma == BUILTIN_PROFILES["dvd-fast"].options.unsharp_luma


def test_resolve_anime_profile_inherits_force_disable_crop() -> None:
    opts = resolve_upscale_options("anime")
    assert opts.force_disable_crop is True


def test_resolve_unknown_profile_raises() -> None:
    with pytest.raises(ValueError):
        resolve_upscale_options("bogus")


def test_resolve_default_profile_is_dvd() -> None:
    opts_default = resolve_upscale_options()
    opts_dvd = resolve_upscale_options("dvd")
    assert opts_default.crf == opts_dvd.crf
    assert opts_default.preset == opts_dvd.preset
    assert opts_default.target_height == opts_dvd.target_height


def test_resolve_returns_upscale_options_instance() -> None:
    result = resolve_upscale_options("1080p")
    assert isinstance(result, UpscaleOptions)
