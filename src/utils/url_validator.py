from __future__ import annotations

from urllib.parse import urlparse


def is_valid_url(value: str) -> bool:
    """Return True when value looks like an absolute HTTP(S) URL."""
    try:
        parsed = urlparse(value)
    except ValueError:
        return False
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def classify_platform(url: str) -> str:
    """Classify known media platforms from a URL hostname."""
    try:
        parsed = urlparse(url)
    except ValueError:
        return "unknown"

    host = parsed.netloc.lower()
    if "youtube.com" in host or "youtu.be" in host:
        return "youtube"
    if "soundcloud.com" in host:
        return "soundcloud"
    if "vimeo.com" in host:
        return "vimeo"
    return "unknown"
