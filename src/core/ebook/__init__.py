"""Core e-book processing package."""

from .models import BookIdentity, BookMetadata
from .cover import CoverImage, CoverProvider, CoverSelector, CoverService, GoogleBooksCoverProvider, OpenLibraryCoverProvider
from .normalization import EpubValidator, EbookNormalizer, MetadataEmbedder, NormalizationResult, TocGenerator, ValidationResult

__all__ = [
    "BookIdentity",
    "BookMetadata",
    "CoverImage",
    "CoverProvider",
    "CoverSelector",
    "CoverService",
    "GoogleBooksCoverProvider",
    "OpenLibraryCoverProvider",
    "EpubValidator",
    "EbookNormalizer",
    "MetadataEmbedder",
    "NormalizationResult",
    "TocGenerator",
    "ValidationResult",
]