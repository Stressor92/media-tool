from __future__ import annotations

from utils.ytdlp_runner import VideoInfo
from core.video.trailer_search import TrailerSearchService


class FakeRunner:
    def __init__(self) -> None:
        self.queries: list[str] = []

    def search(self, query: str, max_results: int = 5, timeout_seconds: int = 30) -> list[VideoInfo]:
        del max_results, timeout_seconds
        self.queries.append(query)

        if query.endswith("en"):
            return []

        return [
            VideoInfo(
                title="Oldboy Official Trailer Deutsch HD",
                url="https://youtube.com/watch?v=de123",
                uploader="Constantin Film",
                view_count=120_000,
            ),
            VideoInfo(
                title="Oldboy fan made teaser",
                url="https://youtube.com/watch?v=bad",
            ),
        ]


def test_search_falls_back_to_second_language() -> None:
    runner = FakeRunner()
    service = TrailerSearchService(runner)

    result = service.search_trailer(
        movie_name="Oldboy",
        year=2003,
        preferred_languages=("en", "de"),
    )

    assert result.found is True
    assert result.language == "de"
    assert result.video_info is not None
    assert result.video_info.url.endswith("de123")
    assert len(runner.queries) == 2
    assert runner.queries[0].endswith("en")
    assert runner.queries[1].endswith("de")


def test_search_prefers_official_trailer() -> None:
    class SingleLangRunner:
        def search(self, query: str, max_results: int = 5, timeout_seconds: int = 30) -> list[VideoInfo]:
            del query, max_results, timeout_seconds
            return [
                VideoInfo(
                    title="Movie clip behind the scenes",
                    url="https://youtube.com/watch?v=clip",
                    view_count=3_000_000,
                ),
                VideoInfo(
                    title="Movie Official Trailer",
                    url="https://youtube.com/watch?v=official",
                    view_count=100_000,
                ),
            ]

    service = TrailerSearchService(SingleLangRunner())
    result = service.search_trailer("Movie", 2022, preferred_languages=("en",))

    assert result.found is True
    assert result.video_info is not None
    assert result.video_info.url.endswith("official")
