"""
src/core/subtitles/subtitle_match_verifier.py

Whisper-based verification for suspicious subtitle matches.
"""

from __future__ import annotations

import logging
import re
import tempfile
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path
from typing import Literal

from core.translation.subtitle_parser import parse_subtitle_file
from core.video.whisper_engine import WhisperConfig, WhisperEngine, WhisperModel
from utils.ffmpeg_runner import run_ffmpeg

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class VerificationWindow:
    name: str
    start_seconds: float
    duration_seconds: float


@dataclass(frozen=True)
class VerificationWindowScore:
    window_name: str
    text_similarity: float
    average_offset_seconds: float | None
    subtitle_segment_count: int
    asr_segment_count: int


@dataclass(frozen=True)
class SubtitleVerificationResult:
    status: Literal["pass", "reject", "uncertain", "skipped"]
    confidence_score: float
    message: str
    average_text_similarity: float = 0.0
    average_offset_seconds: float | None = None
    drift_trend_seconds: float | None = None
    window_scores: list[VerificationWindowScore] = field(default_factory=list)


class SubtitleMatchVerifier:
    """Verify subtitle plausibility by comparing sampled ASR text with subtitle text."""

    MAX_WINDOW_COUNT = 2
    HARD_REJECT_TEXT_SIMILARITY = 0.35
    PASS_TEXT_SIMILARITY = 0.60
    HARD_REJECT_AVG_OFFSET_SECONDS = 15.0
    HARD_REJECT_DRIFT_TREND_SECONDS = 8.0
    LINEAR_DRIFT_TREND_SECONDS = 2.5

    def verify(
        self,
        video_path: Path,
        subtitle_path: Path,
        *,
        video_duration: float,
        language: str = "en",
        model: WhisperModel | str = WhisperModel.TINY,
    ) -> SubtitleVerificationResult:
        if video_duration <= 0:
            return SubtitleVerificationResult(
                status="skipped",
                confidence_score=0.0,
                message="Whisper verification skipped: video duration unavailable",
            )

        try:
            subtitle_document = parse_subtitle_file(subtitle_path)
        except Exception as exc:
            return SubtitleVerificationResult(
                status="reject",
                confidence_score=0.0,
                message=f"Failed to parse subtitle for verification: {exc}",
            )

        windows = self._build_windows(video_duration)
        if not windows:
            return SubtitleVerificationResult(
                status="skipped",
                confidence_score=0.0,
                message="Whisper verification skipped: no valid sample windows",
            )

        normalized_model = model if isinstance(model, WhisperModel) else WhisperModel(model)
        whisper = WhisperEngine(WhisperConfig(model=normalized_model, language=(language or "en"), output_format="srt"))

        window_scores: list[VerificationWindowScore] = []
        signed_offsets: list[float] = []

        with tempfile.TemporaryDirectory(prefix="subtitle-verify-") as temp_dir_name:
            temp_dir = Path(temp_dir_name)

            for idx, window in enumerate(windows, 1):
                clip_wav = temp_dir / f"clip_{idx}.wav"
                clip_srt = temp_dir / f"clip_{idx}.srt"

                clip_result = self._extract_clip(video_path, clip_wav, window)
                if not clip_result:
                    logger.warning("Failed to extract verification clip for %s", window.name)
                    continue

                transcription = whisper.transcribe(
                    clip_wav,
                    clip_srt,
                    detect_hallucinations=False,
                )
                if not transcription.success or transcription.srt_path is None:
                    logger.warning(
                        "Whisper verification transcription failed for %s: %s", window.name, transcription.error_message
                    )
                    continue

                try:
                    asr_document = parse_subtitle_file(transcription.srt_path)
                except Exception as exc:
                    logger.warning("Failed to parse Whisper verification output for %s: %s", window.name, exc)
                    continue

                score, signed_offset = self._score_window(
                    subtitle_document=subtitle_document,
                    asr_document=asr_document,
                    window=window,
                )
                window_scores.append(score)
                if signed_offset is not None:
                    signed_offsets.append(signed_offset)

        if not window_scores:
            return SubtitleVerificationResult(
                status="skipped",
                confidence_score=0.0,
                message="Whisper verification skipped: no usable transcription windows",
            )

        average_similarity = sum(score.text_similarity for score in window_scores) / len(window_scores)
        absolute_offsets = [abs(v) for v in signed_offsets]
        average_offset = (sum(absolute_offsets) / len(absolute_offsets)) if absolute_offsets else None
        drift_trend = abs(signed_offsets[-1] - signed_offsets[0]) if len(signed_offsets) >= 2 else 0.0

        confidence = self._compute_confidence(
            average_similarity=average_similarity,
            average_offset=average_offset,
            drift_trend=drift_trend,
        )

        if average_similarity < self.HARD_REJECT_TEXT_SIMILARITY:
            return SubtitleVerificationResult(
                status="reject",
                confidence_score=confidence,
                message=(
                    "Whisper verification rejected subtitle: very low text similarity " f"({average_similarity:.2f})"
                ),
                average_text_similarity=average_similarity,
                average_offset_seconds=average_offset,
                drift_trend_seconds=drift_trend,
                window_scores=window_scores,
            )

        if average_offset is not None and (
            average_offset > self.HARD_REJECT_AVG_OFFSET_SECONDS and drift_trend > self.HARD_REJECT_DRIFT_TREND_SECONDS
        ):
            return SubtitleVerificationResult(
                status="reject",
                confidence_score=confidence,
                message=(
                    "Whisper verification rejected subtitle: timing offset is large and unstable "
                    f"(avg offset {average_offset:.2f}s, drift trend {drift_trend:.2f}s)"
                ),
                average_text_similarity=average_similarity,
                average_offset_seconds=average_offset,
                drift_trend_seconds=drift_trend,
                window_scores=window_scores,
            )

        if average_similarity >= self.PASS_TEXT_SIMILARITY:
            return SubtitleVerificationResult(
                status="pass",
                confidence_score=confidence,
                message=(
                    "Whisper verification passed "
                    f"(text {average_similarity:.2f}, avg offset {average_offset or 0.0:.2f}s, trend {drift_trend:.2f}s)"
                ),
                average_text_similarity=average_similarity,
                average_offset_seconds=average_offset,
                drift_trend_seconds=drift_trend,
                window_scores=window_scores,
            )

        return SubtitleVerificationResult(
            status="uncertain",
            confidence_score=confidence,
            message=(
                "Whisper verification is inconclusive "
                f"(text {average_similarity:.2f}, avg offset {average_offset or 0.0:.2f}s, trend {drift_trend:.2f}s)"
            ),
            average_text_similarity=average_similarity,
            average_offset_seconds=average_offset,
            drift_trend_seconds=drift_trend,
            window_scores=window_scores,
        )

    def _build_windows(self, video_duration: float) -> list[VerificationWindow]:
        first_len = min(180.0, max(30.0, video_duration))
        first = VerificationWindow(name="first", start_seconds=0.0, duration_seconds=first_len)

        if video_duration <= 240.0:
            return [first]

        middle_len = 90.0
        middle_start = max(0.0, (video_duration / 2.0) - (middle_len / 2.0))
        if middle_start + middle_len > video_duration:
            middle_start = max(0.0, video_duration - middle_len)

        middle = VerificationWindow(name="middle", start_seconds=middle_start, duration_seconds=middle_len)
        return [first, middle][: self.MAX_WINDOW_COUNT]

    def _extract_clip(self, video_path: Path, output_wav: Path, window: VerificationWindow) -> bool:
        result = run_ffmpeg(
            [
                "-y",
                "-ss",
                f"{window.start_seconds:.3f}",
                "-i",
                str(video_path),
                "-t",
                f"{window.duration_seconds:.3f}",
                "-vn",
                "-acodec",
                "pcm_s16le",
                "-ar",
                "16000",
                "-ac",
                "1",
                "-f",
                "wav",
                str(output_wav),
            ]
        )
        return result.success and output_wav.exists()

    def _score_window(
        self, subtitle_document, asr_document, window: VerificationWindow
    ) -> tuple[VerificationWindowScore, float | None]:
        subtitle_window_segments = self._segments_in_window(
            subtitle_document.segments, window.start_seconds, window.duration_seconds
        )

        asr_start = window.start_seconds
        asr_end = window.start_seconds + window.duration_seconds
        asr_segments = []
        for segment in asr_document.segments:
            start_sec = self._timestamp_to_seconds(segment.start) + window.start_seconds
            end_sec = self._timestamp_to_seconds(segment.end) + window.start_seconds
            if end_sec < asr_start or start_sec > asr_end:
                continue
            asr_segments.append((start_sec, end_sec, segment.text))

        subtitle_text = self._normalize_text(" ".join(text for _s, _e, text in subtitle_window_segments))
        asr_text = self._normalize_text(" ".join(text for _s, _e, text in asr_segments))

        if subtitle_text and asr_text:
            similarity = SequenceMatcher(None, subtitle_text, asr_text).ratio()
        else:
            similarity = 0.0

        signed_offset: float | None = None
        if subtitle_window_segments and asr_segments:
            subtitle_anchor = subtitle_window_segments[0][0]
            asr_anchor = asr_segments[0][0]
            signed_offset = subtitle_anchor - asr_anchor

        score = VerificationWindowScore(
            window_name=window.name,
            text_similarity=float(similarity),
            average_offset_seconds=signed_offset,
            subtitle_segment_count=len(subtitle_window_segments),
            asr_segment_count=len(asr_segments),
        )
        return score, signed_offset

    def _segments_in_window(
        self, segments, start_seconds: float, duration_seconds: float
    ) -> list[tuple[float, float, str]]:
        end_seconds = start_seconds + duration_seconds
        window_segments: list[tuple[float, float, str]] = []
        for segment in segments:
            seg_start = self._timestamp_to_seconds(segment.start)
            seg_end = self._timestamp_to_seconds(segment.end)
            if seg_end < start_seconds or seg_start > end_seconds:
                continue
            window_segments.append((seg_start, seg_end, segment.text))
        return window_segments

    @staticmethod
    def _normalize_text(value: str) -> str:
        lowered = value.lower()
        lowered = re.sub(r"<[^>]+>", " ", lowered)
        lowered = re.sub(r"[^a-z0-9\s]", " ", lowered)
        lowered = re.sub(r"\s+", " ", lowered)
        return lowered.strip()

    @staticmethod
    def _timestamp_to_seconds(value: str) -> float:
        normalized = value.strip().replace(".", ",")
        hours, minutes, rest = normalized.split(":")
        seconds, millis = rest.split(",")
        return int(hours) * 3600.0 + int(minutes) * 60.0 + int(seconds) + (int(millis[:3].ljust(3, "0")) / 1000.0)

    def _compute_confidence(self, average_similarity: float, average_offset: float | None, drift_trend: float) -> float:
        offset_component = 1.0
        if average_offset is not None:
            offset_component = max(0.0, 1.0 - min(average_offset, 20.0) / 20.0)

        drift_component = max(0.0, 1.0 - min(drift_trend, 10.0) / 10.0)
        combined = (average_similarity * 0.7) + (offset_component * 0.2) + (drift_component * 0.1)
        return max(0.0, min(1.0, combined))
