"""
src/core/video/subtitle_generator.py

Main orchestration for subtitle generation workflow.
Coordinates audio extraction, Whisper transcription, timing sync, and MKV muxing.

Rules:
- No UI/CLI logic (only return data structures)
- Always create backups before destructive operations
- Comprehensive error handling with rollback
- Log all operations for debugging
"""

from __future__ import annotations

import logging
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from utils import audio_processor
from utils.ffmpeg_runner import FFmpegMuxer
from core.video.subtitle_processor import SubtitleTimingProcessor
from core.video.whisper_engine import WhisperEngine, WhisperConfig, WhisperModel

logger = logging.getLogger(__name__)


@dataclass
class GenerationResult:
    """Result of subtitle generation process.
    
    Attributes:
        success: Whether generation completed successfully
        mkv_path: Path to the input MKV file
        output_mkv_path: Path to the output MKV with subtitles
        audio_duration: Duration of extracted audio in seconds
        srt_path: Path to the generated SRT file
        backup_path: Path to backup of original MKV
        processing_time: Total processing time in seconds
        steps_completed: List of completed processing steps
        warnings: List of non-critical warnings
        error_message: Error message if generation failed
    """
    
    success: bool
    mkv_path: Optional[Path] = None
    output_mkv_path: Optional[Path] = None
    audio_duration: Optional[float] = None
    srt_path: Optional[Path] = None
    backup_path: Optional[Path] = None
    processing_time: float = 0.0
    steps_completed: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    error_message: Optional[str] = None
    
    @property
    def has_subtitles(self) -> bool:
        """True if subtitles were successfully added."""
        return bool(self.success and self.mkv_path and self.mkv_path.exists())

    @property
    def hallucination_warnings(self) -> list[str]:
        """Backward-compatible alias for warnings emitted during transcription."""
        return self.warnings


class SubtitleGenerator:
    """Orchestrates the complete subtitle generation workflow."""
    
    def __init__(
        self,
        whisper_model: WhisperConfig | WhisperModel | str = WhisperModel.LARGE,
        config: WhisperConfig | None = None,
        enhance_mode: str = "light",
        keep_temp_files: bool = False
    ):
        """
        Initialize subtitle generator.
        
        Args:
            whisper_model: WhisperConfig instance or model name
            enhance_mode: Audio enhancement mode
            keep_temp_files: Keep WAV/SRT files after completion
        """
        if config is not None:
            self.whisper_config = config
        elif isinstance(whisper_model, WhisperConfig):
            self.whisper_config = whisper_model
        else:
            model = whisper_model if isinstance(whisper_model, WhisperModel) else WhisperModel(whisper_model)
            self.whisper_config = WhisperConfig(model=model)

        self.enhance_mode = enhance_mode
        self.keep_temp_files = keep_temp_files
        
        # Initialize components
        self.whisper_engine = WhisperEngine(self.whisper_config)
        self.subtitle_processor = SubtitleTimingProcessor()
        self.ffmpeg_muxer = FFmpegMuxer()
        
        self.logger = logging.getLogger(__name__)

    def generate_subtitles(
        self,
        source_mkv: Path | None = None,
        target_mkv: Path | None = None,
        progress_callback: Optional[Callable[[str, float], None]] = None,
        video_path: Path | None = None,
        output_mkv_path: Path | None = None,
        overwrite: bool = False,
        detect_hallucinations: bool = True,
    ) -> GenerationResult:
        """Generate subtitles for source MKV and write to target MKV."""
        source_mkv = source_mkv or video_path
        target_mkv = target_mkv or output_mkv_path

        if source_mkv is None or target_mkv is None:
            return GenerationResult(
                success=False,
                error_message="Both source and target MKV paths are required",
            )

        if not source_mkv.exists():
            return GenerationResult(
                success=False,
                error_message=f"Source file not found: {source_mkv}",
            )

        if target_mkv.exists() and source_mkv != target_mkv and not overwrite:
            return GenerationResult(
                success=False,
                error_message=f"Target file already exists: {target_mkv}",
            )

        if source_mkv != target_mkv:
            target_mkv.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_mkv, target_mkv)

        result = self.generate(
            target_mkv,
            progress_callback=progress_callback,
            detect_hallucinations=detect_hallucinations,
        )
        result.output_mkv_path = target_mkv
        result.audio_duration = getattr(result, 'audio_duration', None)
        return result

    def generate(
        self,
        mkv_path: Path,
        progress_callback: Optional[Callable[[str, float], None]] = None,
        detect_hallucinations: bool = True,
    ) -> GenerationResult:
        """
        Generate subtitles for MKV file.
        
        Workflow:
        1. Validate input MKV
        2. Check prerequisites (no existing English subs)
        3. Extract optimized WAV
        4. Run Whisper transcription
        5. Sync timing to video duration
        6. Validate SRT
        7. Create MKV backup
        8. Mux subtitles into MKV
        9. Cleanup temp files
        
        Args:
            mkv_path: Path to MKV file
            progress_callback: Called with (message, progress_fraction)
            
        Returns:
            GenerationResult with success status and paths
        """
        import time
        start_time = time.time()
        
        result = GenerationResult(success=False, mkv_path=mkv_path, output_mkv_path=mkv_path)
        temp_dir = None
        
        try:
            # Step 1: Validate input
            if progress_callback:
                progress_callback("Validating input file...", 0.0)
            
            validation_result = self._validate_input(mkv_path)
            if not validation_result["valid"]:
                result.error_message = validation_result["error"]
                return result
            
            result.steps_completed.append("input_validation")
            
            # Step 2: Get video duration
            video_duration = validation_result["duration"]
            
            # Step 3: Setup temp directory
            temp_dir = Path(tempfile.mkdtemp(prefix="subtitle_gen_"))
            wav_path = temp_dir / f"{mkv_path.stem}_speech.wav"
            srt_path = temp_dir / f"{mkv_path.stem}.srt"
            
            # Step 4: Extract audio
            if progress_callback:
                progress_callback("Extracting audio for speech recognition...", 0.1)
            
            audio_result = audio_processor.extract_for_speech(
                mkv_path,
                wav_path,
                sample_rate=16000,
                channels=1
            )
            
            if not audio_result.success:
                result.error_message = f"Audio extraction failed: {audio_result.error_message}"
                return result
            
            result.steps_completed.append("audio_extraction")
            
            # Step 5: Run Whisper transcription
            if progress_callback:
                progress_callback("Running Whisper transcription...", 0.3)
            
            transcription_result = self.whisper_engine.transcribe(
                wav_path,
                srt_path,
                progress_callback=lambda msg, prog: progress_callback(
                    f"Transcription: {msg}", 0.3 + prog * 0.4
                ) if progress_callback else None,
                detect_hallucinations=detect_hallucinations,
            )
            
            if not transcription_result.success:
                result.error_message = f"Transcription failed: {transcription_result.error_message}"
                result.warnings.extend([str(w) for w in transcription_result.hallucination_warnings])
                return result
            
            if not transcription_result.is_safe:
                result.error_message = "Transcription contains hallucination warnings"
                result.warnings.extend([str(w) for w in transcription_result.hallucination_warnings])
                return result
            
            result.steps_completed.append("whisper_transcription")
            
            # Step 6: Sync timing
            if progress_callback:
                progress_callback("Synchronizing subtitle timing...", 0.7)
            
            sync_result = self.subtitle_processor.sync_to_video(
                srt_path,
                video_duration,
                transcription_result.wav_duration
            )
            
            if not sync_result.success:
                result.error_message = f"Timing sync failed: {sync_result.error_message}"
                return result
            
            if sync_result.scale_factor != 1.0:
                result.warnings.append(f"Timing scaled by {sync_result.scale_factor:.4f}")
            
            result.steps_completed.append("timing_sync")
            
            # Step 7: Validate SRT
            if progress_callback:
                progress_callback("Validating subtitle format...", 0.75)
            
            validation = self.subtitle_processor.validate_srt(srt_path)
            if not validation.is_valid:
                result.error_message = f"SRT validation failed: {', '.join(validation.errors)}"
                return result
            
            if validation.warnings:
                result.warnings.extend(validation.warnings)
            
            result.steps_completed.append("srt_validation")
            
            # Step 8: Optimize readability
            self.subtitle_processor.optimize_readability(srt_path)
            result.steps_completed.append("readability_optimization")
            
            # Step 9: Create backup
            if progress_callback:
                progress_callback("Creating backup...", 0.8)
            
            backup_path = mkv_path.with_suffix('.mkv.backup')
            shutil.copy2(mkv_path, backup_path)
            result.backup_path = backup_path
            result.steps_completed.append("backup_created")
            
            # Step 10: Mux subtitles
            if progress_callback:
                progress_callback("Adding subtitles to MKV...", 0.9)
            
            mux_result = self.ffmpeg_muxer.add_subtitle_to_mkv(
                mkv_path,
                srt_path,
                language="eng",
                title="English (Whisper AI)"
            )
            
            if not mux_result.success:
                result.error_message = f"Muxing failed: {mux_result.error_message}"
                # Restore backup
                if backup_path.exists():
                    shutil.copy2(backup_path, mkv_path)
                    result.warnings.append("Restored from backup due to muxing failure")
                return result
            
            result.steps_completed.append("subtitle_muxing")
            result.mkv_path = mkv_path
            result.output_mkv_path = mkv_path
            result.srt_path = srt_path if self.keep_temp_files else None
            result.audio_duration = transcription_result.wav_duration
            
            # Step 11: Cleanup
            if not self.keep_temp_files:
                if progress_callback:
                    progress_callback("Cleaning up temporary files...", 0.95)
                self._cleanup_temp_files(temp_dir)
            
            result.success = True
            result.processing_time = time.time() - start_time
            
            if progress_callback:
                progress_callback("Subtitle generation complete!", 1.0)
            
            self.logger.info(f"Successfully generated subtitles for {mkv_path}")
            return result
        
        except Exception as e:
            self.logger.exception(f"Subtitle generation failed: {e}")
            result.error_message = f"Unexpected error: {e}"
            
            # Restore backup on critical error
            if result.backup_path and result.backup_path.exists():
                try:
                    shutil.copy2(result.backup_path, mkv_path)
                    result.warnings.append("Restored from backup due to error")
                except Exception as restore_error:
                    result.warnings.append(f"Failed to restore backup: {restore_error}")
            
            return result
        
        finally:
            # Always cleanup temp dir if not keeping files
            if temp_dir and not self.keep_temp_files:
                try:
                    shutil.rmtree(temp_dir, ignore_errors=True)
                except Exception as e:
                    self.logger.warning(f"Failed to cleanup temp dir {temp_dir}: {e}")
    
    def _validate_input(self, mkv_path: Path) -> dict:
        """
        Validate input MKV file.
        
        Checks:
        - File exists
        - Is MKV format
        - Has video stream
        - No existing English subtitles
        - Get duration
        
        Returns:
            Dict with validation results
        """
        if not mkv_path.exists():
            return {"valid": False, "error": f"File not found: {mkv_path}"}
        
        if mkv_path.suffix.lower() != ".mkv":
            return {"valid": False, "error": f"Not an MKV file: {mkv_path}"}
        
        # Check with ffprobe
        try:
            import subprocess
            
            # Get format info
            result = subprocess.run(
                [
                    "ffprobe", "-v", "error",
                    "-show_entries", "format=format_name,duration",
                    "-of", "default=noprint_wrappers=1:nokey=1",
                    str(mkv_path)
                ],
                capture_output=True,
                # ✅ NO text=True - capture as bytes
                timeout=10
            )
            
            if result.returncode != 0:
                stderr_str = result.stderr.decode("utf-8", errors="replace")
                return {"valid": False, "error": f"FFprobe failed: {stderr_str}"}
            
            stdout_str = result.stdout.decode("utf-8", errors="replace")
            lines = stdout_str.strip().split('\n')
            if len(lines) < 2:
                return {"valid": False, "error": "Cannot determine file format"}
            
            format_name, duration_str = lines
            if "matroska" not in format_name.lower():
                return {"valid": False, "error": f"Not a Matroska/MKV file: {format_name}"}
            
            try:
                duration = float(duration_str)
            except ValueError:
                return {"valid": False, "error": f"Invalid duration: {duration_str}"}
            
            # Check for existing English subtitles
            result = subprocess.run(
                [
                    "ffprobe", "-v", "error",
                    "-select_streams", "s",
                    "-show_entries", "stream_tags=language",
                    "-of", "csv=p=0",
                    str(mkv_path)
                ],
                capture_output=True,
                # ✅ NO text=True - capture as bytes
                timeout=10
            )
            
            if result.returncode == 0:
                stdout_str = result.stdout.decode("utf-8", errors="replace")
                languages = stdout_str.strip().split('\n')
                if any(lang.strip() == "eng" for lang in languages if lang.strip()):
                    return {"valid": False, "error": "MKV already contains English subtitles"}
            
            return {
                "valid": True,
                "duration": duration,
                "format": format_name
            }
        
        except subprocess.TimeoutExpired:
            return {"valid": False, "error": "FFprobe timeout"}
        except Exception as e:
            return {"valid": False, "error": f"Validation failed: {e}"}
    
    def _cleanup_temp_files(self, temp_dir: Path) -> None:
        """Clean up temporary files."""
        try:
            if temp_dir.exists():
                shutil.rmtree(temp_dir, ignore_errors=True)
                self.logger.debug(f"Cleaned up temp directory: {temp_dir}")
        except Exception as e:
            self.logger.warning(f"Failed to cleanup {temp_dir}: {e}")