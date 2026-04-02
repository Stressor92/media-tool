from __future__ import annotations

from core.ebook.models import ConversionProfile, EbookFormat


class ConversionProfiles:
    """Predefined conversion profiles for common reading devices."""

    KINDLE_HIGH_QUALITY = ConversionProfile(
        name="Kindle High Quality",
        output_format=EbookFormat.AZW3,
        quality="high",
        target_device="kindle",
        compress_images=False,
    )

    KINDLE_COMPACT = ConversionProfile(
        name="Kindle Compact",
        output_format=EbookFormat.MOBI,
        quality="medium",
        target_device="kindle",
        compress_images=True,
    )

    KOBO_OPTIMIZED = ConversionProfile(
        name="Kobo Optimized",
        output_format=EbookFormat.EPUB,
        quality="high",
        target_device="tablet",
        compress_images=False,
    )

    GENERIC_EPUB = ConversionProfile(
        name="Generic EPUB",
        output_format=EbookFormat.EPUB,
        quality="high",
        target_device="generic_eink",
        compress_images=False,
    )

    @classmethod
    def get_profile(cls, name: str) -> ConversionProfile | None:
        profiles: dict[str, ConversionProfile] = {
            "kindle_high": cls.KINDLE_HIGH_QUALITY,
            "kindle_compact": cls.KINDLE_COMPACT,
            "kobo": cls.KOBO_OPTIMIZED,
            "epub": cls.GENERIC_EPUB,
        }
        return profiles.get(name.strip().lower())
