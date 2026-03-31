# src/core/translation/formats/ass.py
"""ASS/SSA (Advanced SubStation Alpha) format reader and writer."""
from __future__ import annotations

import re
from pathlib import Path

from core.translation.models import StyleInfo, SubtitleDocument, SubtitleFormat, SubtitleSegment

_ASS_DIALOGUE = re.compile(
    r"^Dialogue:\s*\d+,"           # Layer
    r"(\d:\d{2}:\d{2}\.\d{2}),"   # Start
    r"(\d:\d{2}:\d{2}\.\d{2}),"   # End
    r"([^,]*),"                    # Style
    r"([^,]*),"                    # Actor
    r"[^,]*,[^,]*,[^,]*,[^,]*,"   # margins, effect
    r"(.*)",
    re.MULTILINE,
)
_ASS_TAG = re.compile(r"\{[^}]*\}")
_ASS_STYLE = re.compile(
    r"^Style:\s*([^,]+),"          # Name
    r"([^,]+),"                    # Fontname
    r"(\d+),"                      # Fontsize
    r"&H[0-9A-Fa-f]+&,"           # PrimaryColour
    r"[^,]*,[^,]*,[^,]*,"          # Secondary/Outline/Back
    r"(-?\d+),(-?\d+),(-?\d+),"   # Bold, Italic, Underline
    r"[^,]*,[^,]*,[^,]*,[^,]*,"   # StrikeOut, ScaleX, ScaleY, Spacing
    r"[^,]*,[^,]*,[^,]*,"          # Angle, BorderStyle, Outline
    r"[^,]*,[^,]*,"                # Shadow, Alignment(1)
    r"(\d+)",                      # Alignment(2) – actual numpad value
    re.MULTILINE,
)


def _ass_to_srt_time(t: str) -> str:
    h, m, rest = t.split(":")
    s, cs = rest.split(".")
    return f"{int(h):02d}:{int(m):02d}:{int(s):02d},{int(cs) * 10:03d}"


def _srt_to_ass_time(t: str) -> str:
    h, m, rest = t.split(":")
    s, ms = rest.split(",")
    cs = int(ms) // 10
    return f"{int(h)}:{int(m):02d}:{int(s):02d}.{cs:02d}"


def read(path: Path) -> SubtitleDocument:
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    metadata: dict[str, str] = {}
    for line in text.splitlines():
        if line.startswith("Title:"):
            metadata["title"] = line.split(":", 1)[1].strip()

    styles: list[StyleInfo] = []
    for m in _ASS_STYLE.finditer(text):
        styles.append(StyleInfo(
            name=m.group(1).strip(),
            font_name=m.group(2).strip(),
            font_size=int(m.group(3)),
            bold=(m.group(4) == "-1"),
            italic=(m.group(5) == "-1"),
            underline=(m.group(6) == "-1"),
            alignment=int(m.group(7)),
        ))

    segments: list[SubtitleSegment] = []
    for i, m in enumerate(_ASS_DIALOGUE.finditer(text), start=1):
        raw_text = m.group(5)
        clean = _ASS_TAG.sub("", raw_text).replace(r"\N", "\n").replace(r"\n", "\n")
        segments.append(SubtitleSegment(
            index=i,
            start=_ass_to_srt_time(m.group(1)),
            end=_ass_to_srt_time(m.group(2)),
            text=clean.strip(),
            raw_tags=raw_text,
            style_name=m.group(3).strip() or "Default",
            actor=m.group(4).strip(),
        ))

    return SubtitleDocument(
        segments=segments,
        source_format=SubtitleFormat.ASS,
        source_path=path,
        styles=styles,
        metadata=metadata,
    )


_ASS_HEADER = """\
[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
Title: {title}

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
{styles}
[Events]
Format: Layer, Start, End, Style, Actor, MarginL, MarginR, MarginV, Effect, Text
{events}"""


def _style_to_ass(s: StyleInfo) -> str:
    bold = -1 if s.bold else 0
    italic = -1 if s.italic else 0
    underline = -1 if s.underline else 0

    def hex_color(html: str) -> str:
        h = html.lstrip("#")
        r, g, b = h[0:2], h[2:4], h[4:6]
        return f"&H00{b}{g}{r}&"

    return (
        f"Style: {s.name},{s.font_name},{s.font_size},"
        f"{hex_color(s.primary_color)},&H00FFFFFF&,"
        f"{hex_color(s.outline_color)},{hex_color(s.background_color)},"
        f"{bold},{italic},{underline},0,100,100,0,0,1,2,0,{s.alignment},"
        f"{s.margin_left},{s.margin_right},{s.margin_vertical},1"
    )


def write(doc: SubtitleDocument, path: Path) -> None:
    title = doc.metadata.get("title", path.stem)
    style_list = doc.styles if doc.styles else [StyleInfo()]
    styles_block = "\n".join(_style_to_ass(s) for s in style_list)

    events: list[str] = []
    for seg in doc.segments:
        ass_text = seg.text.replace("\n", r"\N")
        events.append(
            f"Dialogue: 0,{_srt_to_ass_time(seg.start)},{_srt_to_ass_time(seg.end)},"
            f"{seg.style_name},{seg.actor},0,0,0,,{ass_text}"
        )

    content = _ASS_HEADER.format(
        title=title,
        styles=styles_block,
        events="\n".join(events),
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
