from __future__ import annotations

from io import BytesIO

from PIL import Image


class ImageProcessorError(Exception):
    """Raised when image processing fails."""


class ImageProcessor:
    """Small image utility helpers used by ebook cover services."""

    @staticmethod
    def resize_cover(
        image_data: bytes,
        max_width: int = 1600,
        max_height: int = 2400,
        quality: int = 90,
    ) -> bytes:
        """Resize cover art while preserving aspect ratio and output JPEG bytes."""
        try:
            image = Image.open(BytesIO(image_data))
            image.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
            output = BytesIO()
            image.convert("RGB").save(output, format="JPEG", quality=quality, optimize=True)
            return output.getvalue()
        except Exception as exc:
            raise ImageProcessorError(f"Image resize failed: {exc}") from exc

    @staticmethod
    def get_dimensions(image_data: bytes) -> tuple[int, int]:
        """Return width and height for one encoded image."""
        width, height, _ = ImageProcessor.get_image_info(image_data)
        return width, height

    @staticmethod
    def get_image_info(image_data: bytes) -> tuple[int, int, str]:
        """Return width, height, and normalized format string for one image."""
        try:
            image = Image.open(BytesIO(image_data))
            image_format = (image.format or "JPEG").lower()
            return image.width, image.height, image_format
        except Exception as exc:
            raise ImageProcessorError(f"Image inspection failed: {exc}") from exc
