"""
src/core/video/whisper_engine.py

Whisper AI transcription engine with hallucination detection.
Integrates with whisper.cpp CLI or Python whisper/faster-whisper library.

Rules:
- No UI/CLI logic (only return data structures)
- Always validate inputs and outputs
- Detect hallucination loops in real-time
- Stream Whisper output for progress monitoring
"""

from __future__ import annotations

import logging
import re
import subprocess
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Callable, Literal, Optional

logger = logging.getLogger(__name__)


class WhisperModel(str, Enum):
    """Available Whisper model sizes."""
    TINY = "tiny"
    BASE = "base"
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large-v3"


@dataclass
class HallucinationWarning:
    """Warning about potential hallucination detected in transcription.
    
    Attributes:
        type: Category of hallucination (repeated_text, known_pattern, etc.)
        message: Human-readable warning message
        confidence: Confidence level (0.0-1.0)
        details: Additional diagnostic information
    """
    
    type: Literal["repeated_text", "known_pattern", "oversized_output", "long_silence", "timeout"]
    message: str
    confidence: float  # 0.0-1.0
    details: dict = field(default_factory=dict)
    
    def __str__(self) -> str:
        return f"[{self.type.upper()}] {self.message} (confidence: {self.confidence:.0%})"


@dataclass
class TranscriptionResult:
    """Result of Whisper transcription.
    
    Attributes:
        success: Whether transcription completed successfully
        srt_path: Path to generated SRT file
        wav_duration: Duration of input WAV in seconds
        estimated_duration: Estimated transcription duration
        hallucination_warnings: List of detected hallucination warnings
        error_message: Error message if transcription failed
        processing_time: Total transcription time in seconds
    """
    
    success: bool
    srt_path: Optional[Path] = None
    wav_duration: float = 0.0
    estimated_duration: float = 0.0
    hallucination_warnings: list[HallucinationWarning] = field(default_factory=list)
    error_message: Optional[str] = None
    processing_time: float = 0.0
    
    @property
    def is_safe(self) -> bool:
        """True if no critical hallucination warnings."""
        return not any(w.confidence > 0.8 for w in self.hallucination_warnings)


class HallucinationDetector:
    """Detects hallucination patterns in Whisper output."""
    
    # Known hallucination patterns
    KNOWN_PATTERNS = [
        r"thank\s+you\s+for\s+watching",
        r"please\s+subscribe",
        r"MBC.*뉴스",
        r"Amara\.org",
        r"(\[Music\]|\[MUSIC\]){3,}",  # Music tag 3+ times
        r"(\[Silence\]|\[silence\]){5,}",
        r"(\*\*){3,}",  # Multiple asterisks
    ]
    
    # Repeated text detection threshold
    REPETITION_THRESHOLD = 5
    
    # Size ratio thresholds (SRT size vs expected)
    OVERSIZED_RATIO = 10.0  # SRT 10x larger than expected
    
    # Silent period threshold (seconds text with no sound)
    LONG_SILENCE_THRESHOLD = 60.0
    
    def __init__(self):
        self.compiled_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in self.KNOWN_PATTERNS]
        self.logger = logging.getLogger(__name__)
    
    def detect(
        self,
        srt_path: Path,
        wav_duration: float
    ) -> list[HallucinationWarning]:
        """
        Analyze SRT file for hallucination indicators.
        
        Args:
            srt_path: Path to generated SRT file
            wav_duration: Duration of WAV file in seconds
            
        Returns:
            List of HallucinationWarning objects
        """
        warnings = []
        
        if not srt_path.exists():
            warnings.append(HallucinationWarning(
                type="timeout",
                message="SRT file not created (possible timeout or error)",
                confidence=1.0
            ))
            return warnings
        
        try:
            with open(srt_path, "r", encoding="utf-8") as f:
                srt_content = f.read()
        except Exception as e:
            self.logger.error(f"Failed to read SRT: {e}")
            warnings.append(HallucinationWarning(
                type="timeout",
                message=f"SRT file read error: {e}",
                confidence=0.9
            ))
            return warnings
        
        # Check 1: Known hallucination patterns
        pattern_warnings = self._check_known_patterns(srt_content)
        warnings.extend(pattern_warnings)
        
        # Check 2: Repeated identical lines
        repetition_warnings = self._check_repeated_lines(srt_content)
        warnings.extend(repetition_warnings)
        
        # Check 3: Oversized output
        size_warnings = self._check_oversized_output(srt_path, wav_duration)
        warnings.extend(size_warnings)
        
        # Check 4: Long silence with text
        silence_warnings = self._check_long_silence(srt_content)
        warnings.extend(silence_warnings)
        
        return warnings
    
    def _check_known_patterns(self, srt_content: str) -> list[HallucinationWarning]:
        """Check for known hallucination patterns."""
        warnings = []
        
        for pattern in self.compiled_patterns:
            matches = pattern.findall(srt_content)
            if matches:
                # Count occurrences
                count = len(matches)
                confidence = min(count / 5, 1.0)  # Max 100% at 5+ matches
                
                warnings.append(HallucinationWarning(
                    type="known_pattern",
                    message=f"Known hallucination pattern detected: '{matches[0][:50]}' ({count} times)",
                    confidence=confidence,
                    details={"pattern": pattern.pattern, "count": count}
                ))
        
        return warnings
    
    def _check_repeated_lines(self, srt_content: str) -> list[HallucinationWarning]:
        """Check for repeated identical subtitle lines."""
        warnings = []
        
        # Extract subtitle texts by splitting into blocks
        blocks = re.split(r'\n\s*\n', srt_content.strip())
        subtitle_lines = []
        
        for block in blocks:
            lines = block.split('\n')
            # Valid SRT block has: index, timestamp, content
            if len(lines) >= 3 and lines[0].isdigit():
                # Content is everything after the timestamp line
                content = '\n'.join(lines[2:]).strip()
                if content:
                    subtitle_lines.append(content)
        
        if not subtitle_lines:
            return warnings
        
        # Check for repeated identical text
        text_counts = {}
        for line in subtitle_lines:
            # Normalize: strip whitespace, lowercase
            normalized = line.strip().lower()
            if normalized:
                text_counts[normalized] = text_counts.get(normalized, 0) + 1
        
        # Find problematic repeats
        for text, count in sorted(text_counts.items(), key=lambda x: x[1], reverse=True):
            if count >= self.REPETITION_THRESHOLD:
                confidence = min(count / (self.REPETITION_THRESHOLD * 2), 1.0)
                warnings.append(HallucinationWarning(
                    type="repeated_text",
                    message=f"Identical subtitle '{text[:50]}' repeated {count} times",
                    confidence=confidence,
                    details={"text": text, "count": count}
                ))
        
        return warnings
    
    def _check_oversized_output(self, srt_path: Path, wav_duration: float) -> list[HallucinationWarning]:
        """Check if SRT file is unusually large compared to WAV duration."""
        warnings = []
        
        srt_size = srt_path.stat().st_size
        
        # Expected: ~0.5 KB per minute of audio (~10 KB per hour)
        expected_size = (wav_duration / 60) * 0.5 * 1024
        
        if expected_size == 0:
            return warnings
        
        size_ratio = srt_size / expected_size
        
        if size_ratio > self.OVERSIZED_RATIO:
            confidence = min(size_ratio / 20, 1.0)  # 100% at 20x
            warnings.append(HallucinationWarning(
                type="oversized_output",
                message=f"SRT file unusually large: {srt_size / 1024:.1f} KB (expected ~{expected_size / 1024:.1f} KB)",
                confidence=confidence,
                details={"srt_size": srt_size, "expected_size": expected_size, "ratio": size_ratio}
            ))
        
        return warnings
    
    def _check_long_silence(self, srt_content: str) -> list[HallucinationWarning]:
        """Check for long silent periods with text (common hallucination)."""
        warnings = []
        
        # Parse timestamp gaps
        entries = re.findall(
            r"(\d{2}):(\d{2}):(\d{2}),(\d{3}) --> (\d{2}):(\d{2}):(\d{2}),(\d{3})\n(.+?)(?:\n\n|$)",
            srt_content,
            re.DOTALL
        )
        
        if len(entries) < 2:
            return warnings
        
        # Check for large gaps between subtitles
        for i in range(len(entries) - 1):
            end_time = self._parse_timestamp(entries[i][4:8])
            start_time = self._parse_timestamp(entries[i + 1][0:4])
            
            gap = start_time - end_time
            
            if gap > self.LONG_SILENCE_THRESHOLD:
                # Large gap with text - suspicious
                warnings.append(HallucinationWarning(
                    type="long_silence",
                    message=f"Large silent gap with subtitle: {gap:.1f}s between subtitles",
                    confidence=0.7,
                    details={"gap_seconds": gap}
                ))
                break  # Only report once
        
        return warnings
    
    @staticmethod
    def _parse_timestamp(time_parts: tuple) -> float:
        """Convert timestamp parts to seconds."""
        h, m, s, ms = int(time_parts[0]), int(time_parts[1]), int(time_parts[2]), int(time_parts[3])
        return h * 3600 + m * 60 + s + ms / 1000


@dataclass
class WhisperConfig:
    """Configuration for Whisper transcription.
    
    Attributes:
        model: Whisper model size (tiny, base, small, medium, large-v3)
        language: ISO 639-1 language code (default: 'en' for English)
        output_format: Output format (srt, vtt, txt)
        device: Computation device (cpu, cuda, mps)
        compute_type: Precision type for faster-whisper (float32, float16, int8)
        temperature: Temperature for output randomness (0.0 = deterministic)
    """
    
    model: WhisperModel = WhisperModel.LARGE
    language: str = "en"
    output_format: Literal["srt", "vtt", "txt"] = "srt"
    device: Literal["cpu", "cuda", "mps"] = "cpu"
    compute_type: str = "default"  # For faster-whisper: float32, float16, int8
    temperature: float = 0.0  # 0 for deterministic, 0-1.0 for varied


class WhisperEngine:
    """Orchestrates Whisper transcription with safety checks."""
    
    # Timeout for transcription (2 hours for safety)
    TRANSCRIPTION_TIMEOUT = 7200
    
    def __init__(self, config: Optional[WhisperConfig] = None):
        self.config = config or WhisperConfig()
        self.detector = HallucinationDetector()
        self.logger = logging.getLogger(__name__)
    
    def transcribe(
        self,
        wav_path: Path,
        output_srt_path: Optional[Path] = None,
        progress_callback: Optional[Callable[[str, float], None]] = None,
        detect_hallucinations: bool = True
    ) -> TranscriptionResult:
        """
        Transcribe WAV file to SRT using Whisper.
        
        Args:
            wav_path: Path to WAV file
            output_srt_path: Where to save SRT (default: WAV stem + .srt)
            progress_callback: Called with (message, progress_fraction)
            detect_hallucinations: Run hallucination detection
            
        Returns:
            TranscriptionResult with success status and any warnings
        """
        start_time = time.time()
        
        # Validate input
        if not wav_path.exists():
            return TranscriptionResult(
                success=False,
                error_message=f"WAV file not found: {wav_path}"
            )
        
        output_srt_path = output_srt_path or wav_path.with_suffix(".srt")
        
        # Get WAV duration
        try:
            wav_duration = self._get_audio_duration(wav_path)
            if progress_callback:
                progress_callback(f"WAV duration: {wav_duration:.1f}s", 0.0)
        except Exception as e:
            return TranscriptionResult(
                success=False,
                error_message=f"Failed to get WAV duration: {e}"
            )
        
        # Check duration sanity (between 10s and 24h)
        if wav_duration < 10:
            return TranscriptionResult(
                success=False,
                error_message=f"WAV duration too short: {wav_duration:.1f}s"
            )
        
        if wav_duration > 86400:
            return TranscriptionResult(
                success=False,
                error_message=f"WAV duration too long: {wav_duration:.1f}s (>24h)"
            )
        
        try:
            # Run transcription
            if progress_callback:
                progress_callback("Starting Whisper transcription...", 0.1)
            
            self._run_whisper(wav_path, output_srt_path, progress_callback)
            
            # Check hallucinations
            warnings = []
            if detect_hallucinations:
                if progress_callback:
                    progress_callback("Checking for hallucinations...", 0.9)
                warnings = self.detector.detect(output_srt_path, wav_duration)
            
            elapsed = time.time() - start_time
            
            if progress_callback:
                progress_callback("Transcription complete", 1.0)
            
            return TranscriptionResult(
                success=True,
                srt_path=output_srt_path,
                wav_duration=wav_duration,
                hallucination_warnings=warnings,
                processing_time=elapsed
            )
        
        except TimeoutError as e:
            return TranscriptionResult(
                success=False,
                error_message=f"Transcription timeout: {e}",
                hallucination_warnings=[HallucinationWarning(
                    type="timeout",
                    message="Whisper transcription exceeded timeout (>2 hours)",
                    confidence=1.0
                )]
            )
        except Exception as e:
            self.logger.exception(f"Transcription failed: {e}")
            return TranscriptionResult(
                success=False,
                error_message=f"Transcription failed: {e}"
            )
    
    def _run_whisper(
        self,
        wav_path: Path,
        output_srt_path: Path,
        progress_callback: Optional[Callable[[str, float], None]]
    ) -> None:
        """
        Execute Whisper transcription.
        
        Tries in order:
        1. faster-whisper Python library (if available)
        2. whisper Python library
        3. whisper-cli executable
        """
        # Try faster-whisper first (GPU acceleration possible)
        try:
            self._run_faster_whisper(wav_path, output_srt_path, progress_callback)
            return
        except ImportError:
            self.logger.debug("faster-whisper not available, trying whisper library")
        except Exception as e:
            self.logger.warning(f"faster-whisper failed: {e}, trying whisper CLI")
        
        # Try whisper Python library
        try:
            self._run_whisper_library(wav_path, output_srt_path, progress_callback)
            return
        except ImportError:
            self.logger.debug("whisper library not available, trying whisper-cli")
        except Exception as e:
            self.logger.warning(f"whisper library failed: {e}, trying whisper-cli")
        
        # Fall back to CLI
        self._run_whisper_cli(wav_path, output_srt_path, progress_callback)
    
    def _run_faster_whisper(
        self,
        wav_path: Path,
        output_srt_path: Path,
        progress_callback: Optional[Callable[[str, float], None]]
    ) -> None:
        """Run transcription using faster-whisper library."""
        from faster_whisper import WhisperModel
        
        self.logger.info(f"Using faster-whisper ({self.config.model.value} model)")
        
        model = WhisperModel(
            self.config.model.value,
            device=self.config.device,
            compute_type=self.config.compute_type
        )
        
        segments, _ = model.transcribe(
            str(wav_path),
            language=self.config.language,
            beam_size=5,
            best_of=5
        )
        
        # Convert to SRT
        srt_lines = []
        for idx, segment in enumerate(segments, 1):
            start = self._seconds_to_srt_time(segment.start)
            end = self._seconds_to_srt_time(segment.end)
            text = segment.text.strip()
            
            if text:
                srt_lines.extend([
                    str(idx),
                    f"{start} --> {end}",
                    text,
                    ""
                ])
        
        output_srt_path.write_text("\n".join(srt_lines), encoding="utf-8")
        self.logger.info(f"Transcription saved to {output_srt_path}")
    
    def _run_whisper_library(
        self,
        wav_path: Path,
        output_srt_path: Path,
        progress_callback: Optional[Callable[[str, float], None]]
    ) -> None:
        """Run transcription using openai-whisper library."""
        import whisper
        
        self.logger.info(f"Using whisper library ({self.config.model.value} model)")
        
        model = whisper.load_model(self.config.model.value, device=self.config.device)
        
        result = model.transcribe(
            str(wav_path),
            language=self.config.language,
            temperature=self.config.temperature
        )
        
        # Convert to SRT
        srt_lines = []
        for idx, segment in enumerate(result["segments"], 1):
            start = self._seconds_to_srt_time(segment["start"])
            end = self._seconds_to_srt_time(segment["end"])
            text = segment["text"].strip()
            
            if text:
                srt_lines.extend([
                    str(idx),
                    f"{start} --> {end}",
                    text,
                    ""
                ])
        
        output_srt_path.write_text("\n".join(srt_lines), encoding="utf-8")
        self.logger.info(f"Transcription saved to {output_srt_path}")
    
    def _run_whisper_cli(
        self,
        wav_path: Path,
        output_srt_path: Path,
        progress_callback: Optional[Callable[[str, float], None]]
    ) -> None:
        """Run transcription using whisper-cli executable."""
        self.logger.info(f"Using whisper-cli ({self.config.model.value} model)")
        
        # Default output name (whisper appends .srt)
        output_base = output_srt_path.with_suffix("")
        
        # Try to use local model files from utils/whisper_models
        model_path = self._get_local_model_path()
        
        cmd = [
            "whisper-cpp",  # Use whisper-cpp executable
            "-m", str(model_path),  # Use local model file
            "-f", str(wav_path),
            "-osrt",  # Output SRT format
            "--output-file", str(output_base),
            "--output-dir", str(output_srt_path.parent),
            "-l", self.config.language,
        ]
        
        # Add device-specific options if needed
        if self.config.device == "cuda":
            cmd.extend(["-ng", "1"])  # Use GPU if available
        
        try:
            result = subprocess.run(
                cmd,
                timeout=self.TRANSCRIPTION_TIMEOUT,
                capture_output=True,
                # ✅ NO text=True - capture as bytes
                check=False
            )
            
            if result.returncode != 0:
                stderr_str = result.stderr.decode("utf-8", errors="replace")
                self.logger.error(f"Whisper failed: {stderr_str}")
                raise RuntimeError(f"Whisper exited with code {result.returncode}")
            
            # Verify output was created
            if not output_srt_path.exists():
                raise RuntimeError(f"Whisper did not create output: {output_srt_path}")
            
            self.logger.info(f"Transcription saved to {output_srt_path}")
        
        except subprocess.TimeoutExpired:
            raise TimeoutError(f"Whisper transcription exceeded {self.TRANSCRIPTION_TIMEOUT}s timeout")
    
    def _get_local_model_path(self) -> Path:
        """Get path to local Whisper model file."""
        from pathlib import Path
        
        # Base path to models directory
        models_dir = Path(__file__).parent.parent.parent / "utils" / "whisper_models"
        
        # Map model names to actual files
        model_files = {
            "tiny": "ggml-tiny.bin",  # Not in directory, will fallback
            "base": "ggml-base.bin",  # Not in directory, will fallback
            "small": "small.pt",      # Use .pt for Python libraries
            "medium": "medium.pt",    # Use .pt for Python libraries
            "large-v3": "ggml-large-v3.bin",  # Use .bin for whisper-cpp
        }
        
        model_name = self.config.model.value
        model_file = model_files.get(model_name, f"ggml-{model_name}.bin")
        model_path = models_dir / model_file
        
        # Check if local model exists
        if model_path.exists():
            self.logger.info(f"Using local model: {model_path}")
            return model_path
        else:
            # Fallback to model name (let whisper-cli download)
            self.logger.warning(f"Local model not found: {model_path}, using model name")
            return Path(model_name)
    
    @staticmethod
    def _get_audio_duration(wav_path: Path) -> float:
        """Get WAV file duration in seconds."""
        try:
            import wave
            with wave.open(str(wav_path), "rb") as wav:
                frames = wav.getnframes()
                rate = wav.getframerate()
                return frames / rate
        except Exception:
            # Fallback: use ffprobe
            try:
                result = subprocess.run(
                    [
                        "ffprobe", "-v", "error",
                        "-show_entries", "format=duration",
                        "-of", "default=noprint_wrappers=1:nokey=1:0",
                        str(wav_path)
                    ],
                    capture_output=True,
                    # ✅ NO text=True - capture as bytes
                    timeout=10
                )
                stdout_str = result.stdout.decode("utf-8", errors="replace")
                return float(stdout_str.strip())
            except Exception as e:
                raise RuntimeError(f"Cannot get duration: {e}")
    
    @staticmethod
    def _seconds_to_srt_time(seconds: float) -> str:
        """Convert seconds to SRT timestamp format (HH:MM:SS,mmm)."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"
