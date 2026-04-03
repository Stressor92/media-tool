# src/core/language_detection/audio_tagger.py
"""
Schreibt das erkannte Sprachkürzel in die MKV-Metadaten
via FFmpeg (lossless remux — kein Re-Encoding).
"""

from __future__ import annotations

import logging
import shutil
import tempfile
from pathlib import Path

from core.language_detection.models import (
    DetectionRequest,
    TaggingResult,
    TaggingStatus,
)
from core.language_detection.pipeline import LanguageDetectionPipeline
from utils.ffmpeg_runner import run_ffmpeg
from utils.ffprobe_runner import probe_file

logger = logging.getLogger(__name__)

_UNDEFINED_LANGS = {"und", "", "unknown", "unk"}


class AudioTagger:
    """
    Erkennt Sprache unlabeled Audio-Tracks und schreibt das
    Ergebnis als Metadaten-Tag zurück in die MKV-Datei.

    Strategie:
    - Nur Spuren mit `und` / leerer Sprache werden verarbeitet
    - Alle anderen Spuren bleiben unberührt
    - Ausgabe: In-Place (Backup optional) oder neue Datei
    """

    def __init__(
        self,
        pipeline: LanguageDetectionPipeline | None = None,
        min_confidence: float = 0.85,
        create_backup: bool = False,
    ) -> None:
        self._pipeline = pipeline or LanguageDetectionPipeline()
        self._min_confidence = min_confidence
        self._create_backup = create_backup

    def tag_file(
        self,
        path: Path,
        dry_run: bool = False,
        force: bool = False,  # Auch bereits gelabelte Spuren überschreiben
    ) -> list[TaggingResult]:
        """
        Verarbeitet alle unlabeled Audio-Spuren einer Datei.
        Gibt eine Liste von TaggingResult (eine pro Spur) zurück.
        """
        if not path.exists():
            return [
                TaggingResult(
                    status=TaggingStatus.FAILED,
                    path=path,
                    stream_index=0,
                    error="Datei nicht gefunden.",
                )
            ]

        probe = probe_file(path)
        audio_streams = [(i, s) for i, s in enumerate(s for s in probe.streams if s.get("codec_type") == "audio")]

        results: list[TaggingResult] = []
        language_assignments: dict[int, str] = {}  # stream_index → language

        for audio_idx, stream in audio_streams:
            existing_lang = (stream.get("tags", {}) or {}).get("language", "und").lower()

            if existing_lang not in _UNDEFINED_LANGS and not force:
                results.append(
                    TaggingResult(
                        status=TaggingStatus.SKIPPED,
                        path=path,
                        stream_index=audio_idx,
                        detected_language=existing_lang,
                        previous_language=existing_lang,
                        error="Sprache bereits gesetzt.",
                    )
                )
                continue

            request = DetectionRequest(
                video_path=path,
                stream_index=audio_idx,
                dry_run=dry_run,
            )
            detection = self._pipeline.detect(request, probe={"streams": probe.streams})

            if detection.language == "und" or detection.confidence < self._min_confidence:
                results.append(
                    TaggingResult(
                        status=TaggingStatus.FAILED,
                        path=path,
                        stream_index=audio_idx,
                        detected_language=detection.language,
                        confidence=detection.confidence,
                        method=detection.method,
                        error=(
                            f"Konfidenz zu niedrig: {detection.confidence:.0%} (Minimum: {self._min_confidence:.0%})"
                        ),
                    )
                )
                continue

            language_assignments[audio_idx] = detection.language
            results.append(
                TaggingResult(
                    status=TaggingStatus.SUCCESS if not dry_run else TaggingStatus.SKIPPED,
                    path=path,
                    stream_index=audio_idx,
                    detected_language=detection.language,
                    previous_language=existing_lang,
                    confidence=detection.confidence,
                    method=detection.method,
                )
            )

        # Alle Sprachzuweisungen in einem einzigen FFmpeg-Aufruf schreiben
        if language_assignments and not dry_run:
            output_path = self._write_language_tags(path, language_assignments)
            for r in results:
                if r.status == TaggingStatus.SUCCESS:
                    r.output_path = output_path

        return results

    def tag_directory(
        self,
        directory: Path,
        recursive: bool = True,
        dry_run: bool = False,
    ) -> list[TaggingResult]:
        pattern = "**/*.mkv" if recursive else "*.mkv"
        files = list(directory.glob(pattern))
        all_results: list[TaggingResult] = []
        for f in files:
            all_results.extend(self.tag_file(f, dry_run=dry_run))
        return all_results

    def _write_language_tags(
        self,
        path: Path,
        assignments: dict[int, str],  # audio_stream_index → iso639-2
    ) -> Path:
        """
        Schreibt Sprachkürzel via FFmpeg Remux (kein Re-Encoding).
        In-Place: schreibt erst in temporäre Datei, dann Rename.
        """
        if self._create_backup:
            backup = path.with_suffix(path.suffix + ".bak")
            shutil.copy2(path, backup)
            logger.info("Backup erstellt: %s", backup.name)

        tmp = tempfile.NamedTemporaryFile(suffix=path.suffix, dir=path.parent, delete=False)
        tmp.close()
        tmp_path = Path(tmp.name)

        # FFmpeg: alle Streams kopieren, Sprach-Tags setzen
        args = ["-y", "-i", str(path), "-map", "0", "-c", "copy"]
        for audio_idx, lang in assignments.items():
            args += [f"-metadata:s:a:{audio_idx}", f"language={lang}"]
        args.append(str(tmp_path))

        result = run_ffmpeg(args)
        if result.success and tmp_path.exists():
            shutil.move(str(tmp_path), str(path))
            logger.info(
                "Sprach-Tags geschrieben: %s → %s",
                path.name,
                assignments,
            )
            return path
        else:
            tmp_path.unlink(missing_ok=True)
            raise RuntimeError(f"FFmpeg Remux fehlgeschlagen: {result.stderr[:200]}")
