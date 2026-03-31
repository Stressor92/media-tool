from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ParsedTitle:
    title: str
    year: int | None
    raw_stem: str


_YEAR_RE = re.compile(r"[\(\[\. _]?((?:19|20)\d{2})[\)\]\. _]?")

_QUALITY_TAGS = re.compile(
    r"\b(BluRay|Blu-Ray|BDRip|BRRip|DVDRip|DVD|WEB-DL|WEBRip|HDTV|"
    r"720p|1080p|2160p|4K|UHD|HDR|x264|x265|HEVC|H\.?264|H\.?265|"
    r"AAC|AC3|DTS|TrueHD|Atmos|REMUX|PROPER|REPACK|EXTENDED|"
    r"THEATRICAL|DIRECTORS\.?CUT|IMAX|German|English|dubbed|"
    r"multi|MULTI)\b.*$",
    re.IGNORECASE,
)


def parse_title(path: Path) -> ParsedTitle:
    folder_result = _try_parse(path.parent.name)
    if folder_result is not None and (
        folder_result.year is not None
        or _clean_title(path.parent.name).lower() == _clean_title(path.stem).lower()
    ):
        return folder_result

    stem_result = _try_parse(path.stem)
    if stem_result is not None:
        return stem_result

    return ParsedTitle(title=_clean_title(path.stem), year=None, raw_stem=path.stem)


def _try_parse(name: str) -> ParsedTitle | None:
    matches = list(_YEAR_RE.finditer(name))
    year_match = matches[-1] if matches else None
    year = int(year_match.group(1)) if year_match else None
    title_raw = name[: year_match.start()].strip() if year_match else name
    title = _clean_title(title_raw)
    if not title or len(title) < 2:
        return None
    return ParsedTitle(title=title, year=year, raw_stem=name)


def _clean_title(raw: str) -> str:
    cleaned = _QUALITY_TAGS.sub("", raw)
    cleaned = re.sub(r"[._]", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" -")
    return cleaned
