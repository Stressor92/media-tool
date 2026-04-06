from __future__ import annotations

from core.download.models import DownloadRequest, MediaType


def _wants_audio_only(request: DownloadRequest) -> bool:
    return request.media_type == MediaType.MUSIC or request.extract_audio


def build_format_string(request: DownloadRequest) -> str:
    """
    Build yt-dlp format selector based on media type.

    VIDEO/SERIES -> best video+audio up to max resolution.
    MUSIC or explicit audio extraction -> best available audio.
    """
    if _wants_audio_only(request):
        return "bestaudio/best"

    height = request.max_resolution
    return (
        f"bestvideo[height<={height}][ext=mp4]+bestaudio[ext=m4a]"
        f"/bestvideo[height<={height}]+bestaudio"
        f"/best[height<={height}]"
    )


def build_postprocessors(request: DownloadRequest) -> list[dict[str, object]]:
    """Build yt-dlp postprocessor chain for a request."""
    processors: list[dict[str, object]] = []

    if _wants_audio_only(request):
        processors.append(
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": request.audio_format,
                "preferredquality": request.audio_quality,
            }
        )
        if request.embed_thumbnail:
            processors.append({"key": "EmbedThumbnail"})
        processors.append({"key": "FFmpegMetadata", "add_metadata": True})

    elif request.media_type in (MediaType.VIDEO, MediaType.SERIES):
        if request.embed_subtitles:
            processors.append({"key": "FFmpegEmbedSubtitle"})
        if request.embed_thumbnail:
            processors.append({"key": "EmbedThumbnail"})
        processors.append({"key": "FFmpegMetadata", "add_metadata": True})

    if request.sponsorblock_remove:
        categories = list(request.sponsorblock_remove)
        processors.append({"key": "SponsorBlock", "categories": categories})
        processors.append(
            {
                "key": "ModifyChapters",
                "remove_sponsor_segments": categories,
            }
        )

    return processors
