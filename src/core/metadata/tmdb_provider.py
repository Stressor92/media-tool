from __future__ import annotations

from typing import Any

from core.metadata.models import ActorInfo, CrewMember, MovieMetadata, TmdbSearchResult
from core.metadata.tmdb_client import TmdbClient


class TmdbProvider:
    def __init__(self, client: TmdbClient) -> None:
        self._client = client

    def search(self, title: str, year: int | None = None, limit: int = 5) -> list[TmdbSearchResult]:
        params: dict[str, Any] = {
            "query": title,
            "include_adult": False,
        }
        if year is not None:
            params["year"] = year

        data = self._client.get("/search/movie", params)
        items = data.get("results", [])
        if not isinstance(items, list):
            return []

        results: list[TmdbSearchResult] = []
        for item in items[:limit]:
            if not isinstance(item, dict) or "id" not in item:
                continue
            release_date = str(item.get("release_date", "") or "")
            result_year = int(release_date[:4]) if len(release_date) >= 4 and release_date[:4].isdigit() else None
            results.append(
                TmdbSearchResult(
                    tmdb_id=int(item["id"]),
                    title=str(item.get("title", "")),
                    original_title=str(item.get("original_title", "")),
                    year=result_year,
                    overview=str(item.get("overview", "")),
                    popularity=float(item.get("popularity", 0.0) or 0.0),
                    vote_average=float(item.get("vote_average", 0.0) or 0.0),
                    vote_count=int(item.get("vote_count", 0) or 0),
                    poster_path=item.get("poster_path"),
                    backdrop_path=item.get("backdrop_path"),
                    genre_ids=[int(gid) for gid in item.get("genre_ids", []) if isinstance(gid, int)],
                )
            )

        return results

    def get_movie_metadata(self, tmdb_id: int) -> MovieMetadata:
        data = self._client.get_with_fallback(
            f"/movie/{tmdb_id}",
            params={"append_to_response": "credits,videos,images,release_dates,keywords"},
        )

        genres = [str(g.get("name", "")) for g in data.get("genres", []) if isinstance(g, dict)]
        studios = [str(p.get("name", "")) for p in data.get("production_companies", []) if isinstance(p, dict)]
        countries = [str(c.get("name", "")) for c in data.get("production_countries", []) if isinstance(c, dict)]

        keywords_data = data.get("keywords", {})
        if not isinstance(keywords_data, dict):
            keywords_data = {}
        keywords = [str(k.get("name", "")) for k in keywords_data.get("keywords", []) if isinstance(k, dict)]

        release = str(data.get("release_date", "") or "")
        year = int(release[:4]) if len(release) >= 4 and release[:4].isdigit() else None

        mpaa = self._extract_certification(data, "DE") or self._extract_certification(data, "US")

        credits = data.get("credits", {})
        if not isinstance(credits, dict):
            credits = {}

        cast: list[ActorInfo] = []
        for member in credits.get("cast", [])[:20]:
            if not isinstance(member, dict):
                continue
            cast.append(
                ActorInfo(
                    name=str(member.get("name", "")),
                    role=str(member.get("character", "")),
                    order=int(member.get("order", 99) or 99),
                    profile_path=member.get("profile_path"),
                    tmdb_id=member.get("id") if isinstance(member.get("id"), int) else None,
                )
            )

        crew: list[CrewMember] = []
        for member in credits.get("crew", []):
            if not isinstance(member, dict):
                continue
            job = str(member.get("job", ""))
            if job in {"Director", "Producer", "Screenplay", "Writer", "Story"}:
                crew.append(
                    CrewMember(
                        name=str(member.get("name", "")),
                        job=job,
                        department=str(member.get("department", "")),
                    )
                )

        images = data.get("images", {})
        if not isinstance(images, dict):
            images = {}

        collection = data.get("belongs_to_collection")
        collection_names: list[str] = []
        if isinstance(collection, dict) and collection.get("name"):
            collection_names = [str(collection["name"])]

        runtime_value = data.get("runtime")
        runtime: int | None
        if isinstance(runtime_value, int):
            runtime = runtime_value
        elif isinstance(runtime_value, float):
            runtime = int(runtime_value)
        elif isinstance(runtime_value, str) and runtime_value.isdigit():
            runtime = int(runtime_value)
        else:
            runtime = None

        return MovieMetadata(
            tmdb_id=tmdb_id,
            imdb_id=data.get("imdb_id") if isinstance(data.get("imdb_id"), str) else None,
            title=str(data.get("title", "")),
            original_title=str(data.get("original_title", "")),
            sort_title=str(data.get("title", "")),
            year=year,
            release_date=release or None,
            overview=str(data.get("overview", "")),
            tagline=str(data.get("tagline", "")),
            runtime=runtime,
            vote_average=float(data.get("vote_average", 0.0) or 0.0),
            vote_count=int(data.get("vote_count", 0) or 0),
            popularity=float(data.get("popularity", 0.0) or 0.0),
            mpaa_rating=mpaa,
            genres=[g for g in genres if g],
            studios=[s for s in studios if s],
            countries=[c for c in countries if c],
            keywords=[k for k in keywords if k][:20],
            cast=sorted(cast, key=lambda actor: actor.order),
            crew=crew,
            collections=collection_names,
            trailer_url=self._extract_trailer(data),
            poster_path=data.get("poster_path") if isinstance(data.get("poster_path"), str) else None,
            backdrop_path=data.get("backdrop_path") if isinstance(data.get("backdrop_path"), str) else None,
            available_posters=images.get("posters", []) if isinstance(images.get("posters", []), list) else [],
            available_backdrops=images.get("backdrops", []) if isinstance(images.get("backdrops", []), list) else [],
            available_logos=images.get("logos", []) if isinstance(images.get("logos", []), list) else [],
        )

    @staticmethod
    def _extract_certification(data: dict[str, Any], country: str) -> str | None:
        release_dates = data.get("release_dates", {})
        if not isinstance(release_dates, dict):
            return None

        results = release_dates.get("results", [])
        if not isinstance(results, list):
            return None

        for item in results:
            if not isinstance(item, dict) or item.get("iso_3166_1") != country:
                continue
            dates = item.get("release_dates", [])
            if not isinstance(dates, list):
                continue
            for release_item in dates:
                if not isinstance(release_item, dict):
                    continue
                certification = str(release_item.get("certification", "")).strip()
                if certification:
                    return certification
        return None

    @staticmethod
    def _extract_trailer(data: dict[str, Any]) -> str | None:
        videos = data.get("videos", {})
        if not isinstance(videos, dict):
            return None

        results = videos.get("results", [])
        if not isinstance(results, list):
            return None

        for video in results:
            if not isinstance(video, dict):
                continue
            if video.get("type") == "Trailer" and video.get("site") == "YouTube":
                key = video.get("key")
                if isinstance(key, str) and key:
                    return f"https://www.youtube.com/watch?v={key}"
        return None
