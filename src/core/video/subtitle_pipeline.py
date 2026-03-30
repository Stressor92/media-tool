# src/core/video/subtitle_pipeline.py
"""
MKV subtitle pipeline: extract → translate → re-mux.

Allows:
    media-tool video subtitle-translate movie.mkv --from en --to de

which:
  1. Extracts the first subtitle track matching src_lang from the MKV
  2. Translates to tgt_lang using SubtitleTranslator
  3. Re-muxes the new subtitle back into the MKV (copy, no re-encode)

The original MKV is overwritten in-place (after a temp-copy backup approach).
Pass dry_run=True to stop before any file write.
"""
from __future__ import annotations

import logging
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from utils.config import get_config
from utils.ffprobe_runner import ProbeResult, probe_file

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class SubtitleTrackInfo:
    """Metadata of one subtitle stream inside an MKV."""
    stream_index: int       # global stream index in the container
    sub_index: int          # subtitle-only index (0, 1, 2 …)
    codec_name: str         # srt, ass, subrip, webvtt, …
    language: str           # ISO 639-2 or 639-1 (or "und")
    title: str = ""


@dataclass
class MkvTranslationResult:
    """Result of one full extract → translate → remux operation."""
    success: bool
    source_path: Path
    output_path: Optional[Path] = None
    error_message: str = ""
    extracted_sub: Optional[Path] = None
    translated_sub: Optional[Path] = None


# ---------------------------------------------------------------------------
# Public class
# ---------------------------------------------------------------------------

class SubtitleMuxer:
    """
    Thin wrapper around ffmpeg / ffprobe for MKV subtitle operations.

    Only the pure IO / subprocess layer lives here.
    Translation is delegated to SubtitleTranslator.
    """

    def __init__(self) -> None:
        cfg = get_config()
        self._ffmpeg_bin: str = getattr(cfg.tools, "ffmpeg", "ffmpeg")
        self._ffprobe_bin: str = getattr(cfg.tools, "ffprobe", "ffprobe")

    # ------------------------------------------------------------------
    # Probe
    # ------------------------------------------------------------------

    def list_subtitle_tracks(self, video_path: Path) -> list[SubtitleTrackInfo]:
        """Return all subtitle streams found in *video_path*."""
        probe = probe_file(video_path)
        if probe.failed:
            logger.warning("probe failed for %s", video_path)
            return []

        streams = probe.data.get("streams", [])
        tracks: list[SubtitleTrackInfo] = []
        sub_idx = 0
        for stream in streams:
            if stream.get("codec_type") != "subtitle":
                continue
            tags = stream.get("tags", {})
            lang = tags.get("language", "und")
            title = tags.get("title", "")
            codec = stream.get("codec_name", "unknown")
            tracks.append(SubtitleTrackInfo(
                stream_index=stream["index"],
                sub_index=sub_idx,
                codec_name=codec,
                language=lang,
                title=title,
            ))
            sub_idx += 1
        return tracks

    def find_track_by_language(
        self,
        video_path: Path,
        language: str,
    ) -> Optional[SubtitleTrackInfo]:
        """
        Find the first subtitle track whose language matches *language*.

        Handles both ISO 639-1 ("en") and ISO 639-2 ("eng") codes by comparing
        the first two characters.
        """
        lang_short = language[:2].lower()
        for track in self.list_subtitle_tracks(video_path):
            if track.language[:2].lower() == lang_short:
                return track
        return None

    # ------------------------------------------------------------------
    # Extract
    # ------------------------------------------------------------------

    def extract(
        self,
        video_path: Path,
        sub_index: int = 0,
        output_path: Optional[Path] = None,
    ) -> Path:
        """
        Extract the subtitle stream at *sub_index* to an SRT file.

        Parameters
        ----------
        video_path:  Source MKV/video file.
        sub_index:   Subtitle-stream index (0 = first subtitle track).
        output_path: Destination path; auto-generated in a temp dir if None.

        Returns
        -------
        Path to the extracted .srt file.

        Raises
        ------
        RuntimeError if ffmpeg exits with a non-zero return code.
        """
        from utils.ffmpeg_runner import run_ffmpeg

        if output_path is None:
            tmp_dir = Path(tempfile.mkdtemp())
            output_path = tmp_dir / f"{video_path.stem}.track{sub_index}.srt"

        args = [
            "-y",
            "-i", str(video_path),
            "-map", f"0:s:{sub_index}",
            str(output_path),
        ]
        result = run_ffmpeg(args)
        if result.return_code != 0:
            raise RuntimeError(
                f"ffmpeg extract failed (rc={result.return_code}): {result.stderr[-500:]}"
            )
        if not output_path.exists():
            raise RuntimeError(f"ffmpeg produced no output file at {output_path}")
        logger.debug("Extracted subtitle track %d → %s", sub_index, output_path)
        return output_path

    # ------------------------------------------------------------------
    # Mux
    # ------------------------------------------------------------------

    def mux(
        self,
        video_path: Path,
        subtitle_path: Path,
        language: str,
        output_path: Optional[Path] = None,
        title: str = "",
        forced: bool = False,
        default: bool = False,
        overwrite: bool = True,
    ) -> Path:
        """
        Re-mux *subtitle_path* into *video_path*, outputting *output_path*.

        All existing streams are copied (no re-encode).  The new subtitle is
        appended as an additional track.

        Parameters
        ----------
        video_path:    Source MKV.
        subtitle_path: The translated .srt / .vtt to add.
        language:      ISO 639-2 language code for the new track (e.g. "ger", "deu").
        output_path:   Output MKV; defaults to a temp file, then replaces source.
        title:         Human-readable track title (e.g. "Deutsch").
        forced:        Set the forced flag on the new track.
        default:       Set the default flag on the new track.
        overwrite:     Allow overwriting an existing output file.

        Returns
        -------
        Path to the output MKV.
        """
        from utils.ffmpeg_runner import run_ffmpeg

        replace_in_place = output_path is None
        if replace_in_place:
            tmp_fd, tmp_path_str = tempfile.mkstemp(suffix=".mkv")
            import os
            os.close(tmp_fd)
            output_path = Path(tmp_path_str)

        sub_track_idx = 1  # index of the newly mapped subtitle in output
        metadata_args = [
            f"-metadata:s:s:{sub_track_idx}", f"language={language}",
        ]
        if title:
            metadata_args += [f"-metadata:s:s:{sub_track_idx}", f"title={title}"]
        if forced:
            metadata_args += [f"-disposition:s:{sub_track_idx}", "forced"]
        if default:
            metadata_args += [f"-disposition:s:{sub_track_idx}", "default"]

        args = [
            ("-y" if overwrite else "-n"),
            "-i", str(video_path),
            "-i", str(subtitle_path),
            "-map", "0",
            "-map", "1:0",
            "-c", "copy",
            *metadata_args,
            str(output_path),
        ]
        result = run_ffmpeg(args)
        if result.return_code != 0:
            raise RuntimeError(
                f"ffmpeg mux failed (rc={result.return_code}): {result.stderr[-500:]}"
            )

        if replace_in_place:
            # Atomically replace the source file
            shutil.move(str(output_path), str(video_path))
            return video_path

        assert output_path is not None  # guaranteed: replace_in_place covers the None case
        return output_path


# ---------------------------------------------------------------------------
# High-level pipeline function
# ---------------------------------------------------------------------------

def translate_mkv_subtitles(
    video_path: Path,
    source_lang: str,
    target_lang: str,
    backend: str = "opus-mt",
    model_size: str = "big",
    output_path: Optional[Path] = None,
    overwrite: bool = False,
    dry_run: bool = False,
    # SubtitleTranslator knobs forwarded as-is
    chunk_size: int = 4,
    max_chars_per_chunk: int = 250,
    preserve_tags: bool = True,
    line_wrap: bool = True,
    max_line_length: int = 40,
    max_lines: int = 2,
) -> MkvTranslationResult:
    """
    Full extract → translate → remux pipeline for one MKV file.

    Parameters
    ----------
    video_path:    Input MKV.
    source_lang:   Source subtitle language to look for (ISO 639-1, e.g. "en").
    target_lang:   Target translation language (ISO 639-1, e.g. "de").
    backend:       Translation backend ("opus-mt" | "argos").
    model_size:    Model size ("standard" | "big").
    output_path:   Output MKV; if None the source file is updated in-place.
    overwrite:     Overwrite the output file if it already exists.
    dry_run:       Perform all checks but don't write any files.

    Returns
    -------
    MkvTranslationResult
    """
    from core.translation.models import LanguagePair
    from core.translation.subtitle_translator import SubtitleTranslator

    muxer = SubtitleMuxer()

    # Check source file
    if not video_path.exists():
        return MkvTranslationResult(
            success=False,
            source_path=video_path,
            error_message=f"File not found: {video_path}",
        )

    # Find the subtitle track for source_lang
    track = muxer.find_track_by_language(video_path, source_lang)
    if track is None:
        return MkvTranslationResult(
            success=False,
            source_path=video_path,
            error_message=(
                f"No subtitle track with language '{source_lang}' found in {video_path.name}. "
                f"Available tracks: {[t.language for t in muxer.list_subtitle_tracks(video_path)]}"
            ),
        )

    logger.info(
        "Found %s subtitle track (stream %d) in %s",
        track.language, track.stream_index, video_path.name,
    )

    if dry_run:
        return MkvTranslationResult(
            success=True,
            source_path=video_path,
            output_path=output_path or video_path,
        )

    # Extract subtitle to temp file
    try:
        extracted = muxer.extract(video_path, sub_index=track.sub_index)
    except RuntimeError as exc:
        return MkvTranslationResult(
            success=False,
            source_path=video_path,
            error_message=f"Extraction failed: {exc}",
        )

    # Translate
    st = SubtitleTranslator(
        chunk_size=chunk_size,
        max_chars_per_chunk=max_chars_per_chunk,
        preserve_tags=preserve_tags,
        line_wrap=line_wrap,
        max_line_length=max_line_length,
        max_lines=max_lines,
    )
    pair = LanguagePair(source=source_lang, target=target_lang)
    trans_result = st.translate_file(
        source_path=extracted,
        language_pair=pair,
        backend=backend,
        model_size=model_size,
        overwrite=True,  # temp file, always overwrite
    )

    if not trans_result.output_path or not trans_result.output_path.exists():
        return MkvTranslationResult(
            success=False,
            source_path=video_path,
            extracted_sub=extracted,
            error_message=f"Translation produced no output: {trans_result.error_message}",
        )

    # Mux translated subtitle back into MKV
    # Map ISO 639-1 → ISO 639-2 for MKV metadata
    _ISO1_TO_ISO2 = {"en": "eng", "de": "ger", "fr": "fre", "es": "spa"}
    lang3 = _ISO1_TO_ISO2.get(target_lang, target_lang)

    try:
        out = muxer.mux(
            video_path=video_path,
            subtitle_path=trans_result.output_path,
            language=lang3,
            output_path=output_path,
            title=lang3.capitalize(),
            overwrite=overwrite or (output_path is None),
        )
    except RuntimeError as exc:
        return MkvTranslationResult(
            success=False,
            source_path=video_path,
            extracted_sub=extracted,
            translated_sub=trans_result.output_path,
            error_message=f"Mux failed: {exc}",
        )

    return MkvTranslationResult(
        success=True,
        source_path=video_path,
        output_path=out,
        extracted_sub=extracted,
        translated_sub=trans_result.output_path,
    )
