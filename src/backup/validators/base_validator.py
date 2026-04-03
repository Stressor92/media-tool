from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from ..models import ValidationResult


class AbstractValidator(ABC):
    @abstractmethod
    def validate(self, original_path: Path, output_path: Path) -> ValidationResult:
        """Validate output against original and return a detailed validation result."""
