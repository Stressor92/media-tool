from __future__ import annotations

import json
import subprocess
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class FingerprintResult:
    """Result of fingerprint calculation."""
    fingerprint: str
    duration: float
    success: bool
    error_message: Optional[str] = None


class ChromaprintError(Exception):
    """Chromaprint execution failed."""


class ChromaprintTimeoutError(ChromaprintError):
    """Fingerprint calculation timed out."""


class ChromaprintRunner:
    """Wrapper for fpcalc (Chromaprint fingerprinting tool)."""

    def __init__(self, fpcalc_binary: str = "fpcalc"):
        self.fpcalc_binary = fpcalc_binary

    def calculate_fingerprint(
        self,
        audio_path: Path,
        timeout: int = 60,
    ) -> FingerprintResult:
        """Calculate AcoustID fingerprint for an audio file."""

        if not audio_path.exists():
            msg = f"Audio file not found: {audio_path}"
            logger.error(msg)
            return FingerprintResult("", 0.0, False, msg)

        try:
            proc = subprocess.run(
                [self.fpcalc_binary, "-json", "-raw", str(audio_path)],
                capture_output=True,
                timeout=timeout,
                check=True,
            )

            data = json.loads(proc.stdout.decode("utf-8", errors="replace"))
            fingerprint = data.get("fingerprint", "")
            duration = float(data.get("duration", 0.0))

            if not fingerprint or duration <= 0:
                raise ChromaprintError("Incomplete fpcalc output")

            return FingerprintResult(fingerprint, duration, True)

        except subprocess.CalledProcessError as exc:
            err = exc.stderr.decode("utf-8", errors="replace") if exc.stderr is not None else str(exc)
            logger.error("fpcalc error: %s", err)
            return FingerprintResult("", 0.0, False, err)
        except subprocess.TimeoutExpired as exc:
            msg = f"Fingerprint calculation timed out after {timeout}s"
            logger.error(msg)
            raise ChromaprintTimeoutError(msg) from exc
        except json.JSONDecodeError as exc:
            msg = f"Invalid fpcalc output: {exc}"
            logger.error(msg)
            raise ChromaprintError(msg) from exc
        except ChromaprintError as exc:
            logger.error("ChromaprintError: %s", exc)
            return FingerprintResult("", 0.0, False, str(exc))
        except Exception as exc:
            msg = f"Unexpected error during fingerprinting: {exc}"
            logger.error(msg)
            return FingerprintResult("", 0.0, False, msg)
