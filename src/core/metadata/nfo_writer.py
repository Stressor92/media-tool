from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from core.metadata.models import MovieMetadata
from core.metadata.tmdb_client import TmdbClient


def write_movie_nfo(metadata: MovieMetadata, output_path: Path) -> None:
    root = ET.Element("movie")

    def add(tag: str, text: object, attrs: dict[str, str] | None = None) -> None:
        element = ET.SubElement(root, tag, attrs or {})
        element.text = "" if text is None else str(text)

    add("title", metadata.title)
    add("originaltitle", metadata.original_title)
    add("sorttitle", metadata.sort_title or metadata.title)
    add("year", metadata.year)
    add("premiered", metadata.release_date)
    add("plot", metadata.overview)
    add("tagline", metadata.tagline)
    add("runtime", metadata.runtime)
    add("mpaa", metadata.mpaa_rating)
    add("rating", f"{metadata.vote_average:.1f}")
    add("votes", metadata.vote_count)

    ratings = ET.SubElement(root, "ratings")
    rating = ET.SubElement(ratings, "rating", {"name": "tmdb", "max": "10", "default": "true"})
    ET.SubElement(rating, "value").text = f"{metadata.vote_average:.1f}"
    ET.SubElement(rating, "votes").text = str(metadata.vote_count)

    add("uniqueid", metadata.tmdb_id, {"type": "tmdb", "default": "true"})
    if metadata.imdb_id:
        add("uniqueid", metadata.imdb_id, {"type": "imdb"})

    for genre in metadata.genres:
        add("genre", genre)
    for studio in metadata.studios:
        add("studio", studio)
    for country in metadata.countries:
        add("country", country)
    for keyword in metadata.keywords[:10]:
        add("tag", keyword)
    for collection in metadata.collections:
        add("set", collection)

    for member in metadata.crew:
        if member.job == "Director":
            add("director", member.name)
    for member in metadata.crew:
        if member.job in {"Screenplay", "Writer", "Story"}:
            add("credits", member.name)

    for actor in metadata.cast:
        actor_el = ET.SubElement(root, "actor")
        ET.SubElement(actor_el, "name").text = actor.name
        ET.SubElement(actor_el, "role").text = actor.role
        ET.SubElement(actor_el, "order").text = str(actor.order)
        if actor.profile_path:
            ET.SubElement(actor_el, "thumb").text = TmdbClient.image_url(actor.profile_path, "w185")

    if metadata.trailer_url:
        add("trailer", metadata.trailer_url)

    if metadata.poster_path:
        add("thumb", TmdbClient.image_url(metadata.poster_path, "w500"), {"aspect": "poster"})

    if metadata.backdrop_path:
        fanart = ET.SubElement(root, "fanart")
        ET.SubElement(fanart, "thumb").text = TmdbClient.image_url(metadata.backdrop_path, "w1280")

    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8") as handle:
        handle.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        tree.write(handle, encoding="unicode")
