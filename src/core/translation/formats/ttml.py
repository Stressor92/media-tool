# src/core/translation/formats/ttml.py
"""TTML / DFXP (Timed Text Markup Language) format reader and writer."""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

from core.translation.models import (
    PositionInfo,
    StyleInfo,
    SubtitleDocument,
    SubtitleFormat,
    SubtitleSegment,
)

_NS_TTML    = "http://www.w3.org/ns/ttml"
_NS_TTS     = "http://www.w3.org/ns/ttml#styling"
_TIME_RE    = re.compile(r"(\d+):(\d{2}):(\d{2})(?:[.,](\d+))?")


def _ttml_time_to_srt(t: str) -> str:
    m = _TIME_RE.match(t.strip())
    if not m:
        return "00:00:00,000"
    h, mi, s = int(m.group(1)), int(m.group(2)), int(m.group(3))
    ms_raw = m.group(4) or "0"
    ms = int(ms_raw[:3].ljust(3, "0"))
    return f"{h:02d}:{mi:02d}:{s:02d},{ms:03d}"


def _srt_time_to_ttml(t: str) -> str:
    return t.replace(",", ".")


def _collect_text(elem: ET.Element) -> str:
    parts: list[str] = []
    if elem.text:
        parts.append(elem.text)
    for child in elem:
        tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
        if tag == "br":
            parts.append("\n")
        elif tag == "span":
            parts.append(_collect_text(child))
        if child.tail:
            parts.append(child.tail)
    return "".join(parts).strip()


def read(path: Path) -> SubtitleDocument:
    tree = ET.parse(path)
    root = tree.getroot()

    # Dynamic namespace detection
    ns_tt = _NS_TTML
    if root.tag.startswith("{"):
        ns_tt = root.tag.split("}")[0][1:]

    ns_map = {"tt": ns_tt, "tts": _NS_TTS}

    segments: list[SubtitleSegment] = []
    styles: list[StyleInfo] = []
    metadata: dict[str, str] = {}

    # Read lang attribute
    lang = root.attrib.get("{http://www.w3.org/XML/1998/namespace}lang", "unknown")

    for style_el in root.findall(f".//{{{ns_tt}}}style"):
        attrib = style_el.attrib
        sid = attrib.get("{http://www.w3.org/XML/1998/namespace}id", attrib.get("id", "Default"))
        styles.append(StyleInfo(
            name=sid,
            font_name=attrib.get(f"{{{_NS_TTS}}}fontFamily", "Arial"),
            bold=attrib.get(f"{{{_NS_TTS}}}fontWeight", "") == "bold",
            italic=attrib.get(f"{{{_NS_TTS}}}fontStyle", "") == "italic",
        ))

    body = root.find(f".//{{{ns_tt}}}body")
    if body is None:
        return SubtitleDocument([], SubtitleFormat.TTML, path, metadata=metadata)

    for i, p in enumerate(body.iter(f"{{{ns_tt}}}p"), start=1):
        begin = p.attrib.get("begin", "")
        end   = p.attrib.get("end", "")
        text  = _collect_text(p)
        if not text or not begin:
            continue
        region = p.attrib.get("region")
        pos = PositionInfo(region=region) if region else None
        segments.append(SubtitleSegment(
            index=i,
            start=_ttml_time_to_srt(begin),
            end=_ttml_time_to_srt(end),
            text=text,
            style_name=p.attrib.get("style", "Default"),
            position=pos,
        ))

    return SubtitleDocument(
        segments=segments,
        source_format=SubtitleFormat.TTML,
        source_path=path,
        language=lang,
        styles=styles,
        metadata=metadata,
    )


def write(doc: SubtitleDocument, path: Path) -> None:
    ET.register_namespace("",    _NS_TTML)
    ET.register_namespace("tts", _NS_TTS)

    tt = ET.Element("tt", {
        "xmlns":     _NS_TTML,
        "xmlns:tts": _NS_TTS,
        "xml:lang":  doc.language if doc.language != "unknown" else "",
    })
    head    = ET.SubElement(tt, "head")
    styling = ET.SubElement(head, "styling")

    for s in (doc.styles or [StyleInfo()]):
        ET.SubElement(styling, "style", {
            "xml:id":          s.name,
            "tts:fontFamily":  s.font_name,
            "tts:fontSize":    f"{s.font_size}px",
            "tts:fontWeight":  "bold" if s.bold else "normal",
            "tts:fontStyle":   "italic" if s.italic else "normal",
            "tts:color":       s.primary_color,
        })

    body = ET.SubElement(tt, "body")
    div  = ET.SubElement(body, "div")

    for seg in doc.segments:
        p_attrib: dict[str, str] = {
            "begin": _srt_time_to_ttml(seg.start),
            "end":   _srt_time_to_ttml(seg.end),
        }
        if seg.style_name and seg.style_name != "Default":
            p_attrib["style"] = seg.style_name
        if seg.position and seg.position.region:
            p_attrib["region"] = seg.position.region

        p = ET.SubElement(div, "p", p_attrib)
        lines = seg.text.split("\n")
        p.text = lines[0]
        for line in lines[1:]:
            br = ET.SubElement(p, "br")
            br.tail = line

    tree = ET.ElementTree(tt)
    ET.indent(tree, space="  ")
    path.parent.mkdir(parents=True, exist_ok=True)
    tree.write(str(path), encoding="utf-8", xml_declaration=True)
