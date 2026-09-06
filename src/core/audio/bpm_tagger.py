"""BPM analysis and MP3 metadata tagging."""

from __future__ import annotations

import logging
import tempfile
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from enum import Enum, auto
from importlib import import_module
from pathlib import Path
from statistics import median

from utils.ffmpeg_runner import run_ffmpeg

logger = logging.getLogger(__name__)

BPMAnalyzer = Callable[[Path], float | None]


class BPMTaggingStatus(Enum):
    """Result status for BPM tagging operations."""

    UPDATED = auto()
    SKIPPED = auto()
    FAILED = auto()


@dataclass(frozen=True)
class BPMTaggingResult:
    """Outcome for a single MP3 BPM tagging attempt."""

    path: Path
    status: BPMTaggingStatus
    bpm: int | None = None
    existing_bpm: int | None = None
    error: str | None = None


class BPMTagger:
    """Analyze BPM from MP3 audio and write TBPM ID3 metadata."""

    def __init__(self, analyzer: BPMAnalyzer | None = None) -> None:
        self._analyzer = analyzer or self._estimate_bpm_with_librosa

    def tag_file(self, file_path: Path, overwrite: bool = False, dry_run: bool = False) -> BPMTaggingResult:
        """Analyze one MP3 file and write TBPM metadata in-place."""
        if not file_path.exists() or not file_path.is_file():
            return BPMTaggingResult(path=file_path, status=BPMTaggingStatus.FAILED, error="Datei nicht gefunden.")

        if file_path.suffix.lower() != ".mp3":
            return BPMTaggingResult(path=file_path, status=BPMTaggingStatus.SKIPPED, error="Nur MP3 wird unterstützt.")

        try:
            existing_bpm = self._read_existing_bpm(file_path)
        except Exception as exc:
            logger.warning("Could not read existing BPM tag from %s: %s", file_path, exc)
            return BPMTaggingResult(
                path=file_path,
                status=BPMTaggingStatus.FAILED,
                error=f"Bestehender BPM-Tag konnte nicht gelesen werden: {exc}",
            )

        if existing_bpm is not None and not overwrite:
            return BPMTaggingResult(
                path=file_path,
                status=BPMTaggingStatus.SKIPPED,
                bpm=existing_bpm,
                existing_bpm=existing_bpm,
                error="BPM bereits gesetzt.",
            )

        try:
            analyzed = self._analyzer(file_path)
        except Exception as exc:
            logger.warning("BPM analysis failed for %s: %s", file_path, exc)
            return BPMTaggingResult(
                path=file_path,
                status=BPMTaggingStatus.FAILED,
                existing_bpm=existing_bpm,
                error=f"BPM-Analyse fehlgeschlagen: {exc}",
            )

        normalized_bpm = self._normalize_bpm_value(analyzed)
        if normalized_bpm is None:
            return BPMTaggingResult(
                path=file_path,
                status=BPMTaggingStatus.FAILED,
                existing_bpm=existing_bpm,
                error="BPM konnte nicht zuverlässig ermittelt werden.",
            )

        if not dry_run:
            try:
                self._write_bpm_tag(file_path, normalized_bpm)
            except Exception as exc:
                logger.warning("Could not write BPM tag to %s: %s", file_path, exc)
                return BPMTaggingResult(
                    path=file_path,
                    status=BPMTaggingStatus.FAILED,
                    existing_bpm=existing_bpm,
                    error=f"BPM-Tag konnte nicht geschrieben werden: {exc}",
                )

        return BPMTaggingResult(
            path=file_path,
            status=BPMTaggingStatus.UPDATED,
            bpm=normalized_bpm,
            existing_bpm=existing_bpm,
        )

    def tag_directory(
        self,
        directory: Path,
        recursive: bool = True,
        overwrite: bool = False,
        dry_run: bool = False,
    ) -> list[BPMTaggingResult]:
        """Analyze and tag all MP3 files in a directory."""
        if not directory.is_dir():
            return []

        iterator = directory.rglob("*") if recursive else directory.glob("*")
        mp3_files = sorted(
            (path for path in iterator if path.is_file() and path.suffix.lower() == ".mp3"),
            key=lambda path: str(path).lower(),
        )

        return [self.tag_file(path, overwrite=overwrite, dry_run=dry_run) for path in mp3_files]

    @staticmethod
    def _normalize_bpm_value(raw_bpm: float | None) -> int | None:
        """Normalize BPM to a musically plausible range."""
        if raw_bpm is None or raw_bpm <= 0:
            return None

        bpm = float(raw_bpm)
        while bpm < 60:
            bpm *= 2
        while bpm > 200:
            bpm /= 2

        return max(1, int(round(bpm)))

    @staticmethod
    def _parse_bpm_value(raw_value: object) -> int | None:
        try:
            parsed = float(str(raw_value).strip())
        except (TypeError, ValueError):
            return None

        if parsed <= 0:
            return None
        return int(round(parsed))

    def _read_existing_bpm(self, file_path: Path) -> int | None:
        id3 = import_module("mutagen.id3")
        id3_reader = id3.ID3
        id3_no_header_error = id3.ID3NoHeaderError

        try:
            tags = id3_reader(file_path)
        except id3_no_header_error:
            return None

        frames = tags.getall("TBPM")
        if not frames:
            return None

        text_values = getattr(frames[0], "text", None)
        if not text_values:
            return None

        return self._parse_bpm_value(text_values[0])

    def _write_bpm_tag(self, file_path: Path, bpm: int) -> None:
        id3 = import_module("mutagen.id3")
        id3_reader = id3.ID3
        id3_no_header_error = id3.ID3NoHeaderError
        tbpm_frame = id3.TBPM

        try:
            tags = id3_reader(file_path)
        except id3_no_header_error:
            tags = id3_reader()

        tags.delall("TBPM")
        tags.add(tbpm_frame(encoding=3, text=[str(bpm)]))
        tags.save(file_path, v2_version=3)

    def _estimate_bpm_with_librosa(self, file_path: Path) -> float | None:
        """Estimate BPM using two tempo estimators and reject unstable outcomes."""
        try:
            librosa = import_module("librosa")
        except ImportError as exc:
            raise RuntimeError("Für BPM-Analyse wird 'librosa' benötigt.") from exc

        # Skip intro silence/noise and analyze a bounded window for stable, fast batch runs.
        audio, sample_rate = self._load_audio_for_bpm(librosa, file_path)
        if not len(audio):
            return None

        onset_envelope = librosa.onset.onset_strength(y=audio, sr=sample_rate)
        if not len(onset_envelope):
            return None

        beat_tempo_raw, _ = librosa.beat.beat_track(onset_envelope=onset_envelope, sr=sample_rate)
        beat_tempo = self._normalize_bpm_value(self._first_numeric_value(beat_tempo_raw))

        tempo_candidates_raw = librosa.feature.tempo(onset_envelope=onset_envelope, sr=sample_rate, aggregate=None)
        tempo_candidates = [
            value
            for value in (
                self._normalize_bpm_value(item) for item in self._flatten_numeric_values(tempo_candidates_raw)
            )
            if value is not None
        ]
        candidate_tempo = int(round(median(tempo_candidates))) if tempo_candidates else None

        if beat_tempo is None and candidate_tempo is None:
            return None
        if beat_tempo is None:
            return float(candidate_tempo)
        if candidate_tempo is None:
            return float(beat_tempo)

        if abs(beat_tempo - candidate_tempo) > 12:
            return None
        return float((beat_tempo + candidate_tempo) / 2)

    def _load_audio_for_bpm(self, librosa_module: object, file_path: Path) -> tuple[object, int]:
        """Load audio for BPM analysis with retries for short tracks and decoder fallbacks."""
        direct_errors: list[Exception] = []
        for start_offset in (15.0, 0.0):
            try:
                audio, sample_rate = librosa_module.load(
                    str(file_path),
                    sr=22050,
                    mono=True,
                    offset=start_offset,
                    duration=120.0,
                )
                if len(audio):
                    return audio, sample_rate
            except Exception as exc:
                direct_errors.append(exc)

        if direct_errors:
            logger.debug("Direct librosa load failed for %s, trying ffmpeg fallback", file_path, exc_info=True)

        fallback_errors: list[Exception] = []
        for start_offset in (15, 0):
            temp_wav = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            temp_wav.close()
            temp_wav_path = Path(temp_wav.name)

            try:
                result = run_ffmpeg(
                    [
                        "-y",
                        "-ss",
                        str(start_offset),
                        "-i",
                        str(file_path),
                        "-t",
                        "120",
                        "-vn",
                        "-ac",
                        "1",
                        "-ar",
                        "22050",
                        str(temp_wav_path),
                    ]
                )
                if result.failed or not temp_wav_path.exists():
                    stderr_tail = result.stderr.strip()[-300:]
                    raise RuntimeError(f"ffmpeg fallback failed: {stderr_tail or 'unknown ffmpeg error'}")

                audio, sample_rate = librosa_module.load(str(temp_wav_path), sr=22050, mono=True)
                if len(audio):
                    return audio, sample_rate
            except Exception as exc:
                fallback_errors.append(exc)
            finally:
                temp_wav_path.unlink(missing_ok=True)

        original_message = str(direct_errors[-1]) if direct_errors else "keine Audiodaten im Analysefenster"
        fallback_message = str(fallback_errors[-1]) if fallback_errors else "keine Audiodaten im Fallback"
        raise RuntimeError(
            f"Audiodaten konnten nicht gelesen werden ({original_message}; fallback: {fallback_message})"
        )

    @staticmethod
    def _first_numeric_value(value: object) -> float | None:
        if isinstance(value, bool):
            return None
        if isinstance(value, int | float):
            return float(value)
        if hasattr(value, "item"):
            try:
                return float(value.item())
            except (TypeError, ValueError):
                pass
        if isinstance(value, list | tuple) and value:
            return BPMTagger._first_numeric_value(value[0])
        return None

    @staticmethod
    def _flatten_numeric_values(value: object) -> list[float]:
        if isinstance(value, bool):
            return []
        if isinstance(value, int | float):
            return [float(value)]
        if hasattr(value, "tolist"):
            return BPMTagger._flatten_numeric_values(value.tolist())
        if isinstance(value, Iterable) and not isinstance(value, str | bytes):
            flattened: list[float] = []
            for item in value:
                flattened.extend(BPMTagger._flatten_numeric_values(item))
            return flattened
        try:
            return [float(cast_value)] if (cast_value := float(value)) else [cast_value]
        except (TypeError, ValueError):
            return []
