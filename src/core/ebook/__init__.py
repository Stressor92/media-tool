"""Core e-book processing package."""

from .audit import LibraryAuditor, QualityChecker, SeriesAnalyzer
from .conversion import CalibreConversionError, CalibreNotFoundError, CalibreRunner, ConversionProfiles, FormatConverter
from .cover import (
    CoverImage,
    CoverProvider,
    CoverSelector,
    CoverService,
    GoogleBooksCoverProvider,
    OpenLibraryCoverProvider,
)
from .deduplication import DuplicateFinder, FingerprintService, VersionComparator
from .models import (
    AuditReport,
    BookIdentity,
    BookMetadata,
    ConversionProfile,
    ConversionResult,
    DuplicateGroup,
    EbookFormat,
    LibraryStructure,
    ProcessingResult,
)
from .normalization import (
    EbookNormalizer,
    EpubValidator,
    MetadataEmbedder,
    NormalizationResult,
    TocGenerator,
    ValidationResult,
)
from .organization import FolderStructureBuilder, LibraryOrganizer, NamingService, OrganizationResult
from .workflow import BatchProcessor, EbookProcessor, WorkflowConfig

__all__ = [
    "AuditReport",
    "BookIdentity",
    "BookMetadata",
    "EbookFormat",
    "ConversionProfile",
    "ConversionResult",
    "DuplicateGroup",
    "LibraryStructure",
    "ProcessingResult",
    "LibraryAuditor",
    "QualityChecker",
    "SeriesAnalyzer",
    "CoverImage",
    "CoverProvider",
    "CoverSelector",
    "CoverService",
    "GoogleBooksCoverProvider",
    "OpenLibraryCoverProvider",
    "CalibreRunner",
    "CalibreNotFoundError",
    "CalibreConversionError",
    "ConversionProfiles",
    "FormatConverter",
    "NamingService",
    "FolderStructureBuilder",
    "LibraryOrganizer",
    "OrganizationResult",
    "DuplicateFinder",
    "VersionComparator",
    "FingerprintService",
    "EbookProcessor",
    "BatchProcessor",
    "WorkflowConfig",
    "EpubValidator",
    "EbookNormalizer",
    "MetadataEmbedder",
    "NormalizationResult",
    "TocGenerator",
    "ValidationResult",
]
