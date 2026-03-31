import xml.etree.ElementTree as ET
from pathlib import Path

from core.metadata.models import ActorInfo, CrewMember, MovieMetadata
from core.metadata.nfo_writer import write_movie_nfo


def _metadata() -> MovieMetadata:
    return MovieMetadata(
        tmdb_id=27205,
        imdb_id="tt1375666",
        title="Inception",
        original_title="Inception",
        sort_title="Inception",
        year=2010,
        release_date="2010-07-16",
        overview="A thief ...",
        tagline="Your mind ...",
        runtime=148,
        vote_average=8.8,
        vote_count=2_400_000,
        popularity=45.0,
        mpaa_rating="FSK 12",
        genres=["Action", "Sci-Fi"],
        studios=["Warner Bros."],
        countries=["USA"],
        keywords=["heist"],
        cast=[ActorInfo("Leonardo DiCaprio", "Cobb", 0, None)],
        crew=[CrewMember("Christopher Nolan", "Director", "Directing")],
        collections=[],
        trailer_url=None,
        poster_path="/p.jpg",
        backdrop_path="/b.jpg",
        available_posters=[],
        available_backdrops=[],
        available_logos=[],
    )


def test_title(tmp_path: Path) -> None:
    output = tmp_path / "movie.nfo"
    write_movie_nfo(_metadata(), output)
    assert ET.parse(output).getroot().findtext("title") == "Inception"


def test_genres(tmp_path: Path) -> None:
    output = tmp_path / "movie.nfo"
    write_movie_nfo(_metadata(), output)
    genres = [element.text for element in ET.parse(output).getroot().findall("genre")]
    assert "Action" in genres
    assert "Sci-Fi" in genres


def test_actor_with_role(tmp_path: Path) -> None:
    output = tmp_path / "movie.nfo"
    write_movie_nfo(_metadata(), output)
    actor = ET.parse(output).getroot().find("actor")
    assert actor is not None
    assert actor.findtext("name") == "Leonardo DiCaprio"
    assert actor.findtext("role") == "Cobb"


def test_tmdb_uniqueid(tmp_path: Path) -> None:
    output = tmp_path / "movie.nfo"
    write_movie_nfo(_metadata(), output)
    ids = ET.parse(output).getroot().findall("uniqueid")
    tmdb = next(element for element in ids if element.get("type") == "tmdb")
    assert tmdb.text == "27205"


def test_valid_xml(tmp_path: Path) -> None:
    output = tmp_path / "movie.nfo"
    write_movie_nfo(_metadata(), output)
    ET.parse(output)
