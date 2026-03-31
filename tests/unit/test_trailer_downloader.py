from __future__ import annotations

from pathlib import Path

from core.video.movie_folder_scanner import MovieFolder
from core.video.trailer_downloader import TrailerDownloadService
from core.video.trailer_search import TrailerSearchResult
from utils.ytdlp_runner import DownloadResult, VideoInfo


class FakeScanner:
    def __init__(self, folders: list[MovieFolder]) -> None:
        self.folders = folders

    def scan_library(self, root_path: Path, skip_with_trailer: bool = True) -> list[MovieFolder]:
        del root_path, skip_with_trailer
        return self.folders


class FakeSearchService:
    def __init__(self, results: list[TrailerSearchResult]) -> None:
        self.results = results
        self.calls = 0

    def search_trailer(
        self,
        movie_name: str,
        year: int | None = None,
        preferred_languages: tuple[str, ...] = ("en", "de"),
        max_results_per_language: int = 8,
    ) -> TrailerSearchResult:
        del movie_name, year, preferred_languages, max_results_per_language
        result = self.results[self.calls]
        self.calls += 1
        return result


class FakeYtdlp:
    def __init__(self) -> None:
        self.download_calls: list[tuple[str, Path]] = []

    def download(self, url: str, output_path: Path, timeout_seconds: int = 600) -> DownloadResult:
        del timeout_seconds
        self.download_calls.append((url, output_path))
        return DownloadResult(success=True, file_path=output_path)


def test_process_library_respects_max_downloads(tmp_path: Path) -> None:
    folders = [
        MovieFolder(tmp_path / "Movie A (2020)", "Movie A", 2020, False),
        MovieFolder(tmp_path / "Movie B (2021)", "Movie B", 2021, False),
    ]

    search_results = [
        TrailerSearchResult(
            found=True,
            video_info=VideoInfo(title="A Official Trailer", url="https://youtube.com/watch?v=a"),
            language="en",
        ),
        TrailerSearchResult(
            found=True,
            video_info=VideoInfo(title="B Official Trailer", url="https://youtube.com/watch?v=b"),
            language="en",
        ),
    ]

    ytdlp = FakeYtdlp()
    service = TrailerDownloadService(
        ytdlp_runner=ytdlp,
        scanner=FakeScanner(folders),
        search_service=FakeSearchService(search_results),
    )

    results = service.process_library(
        library_path=tmp_path,
        preferred_languages=("en", "de"),
        max_downloads=1,
    )

    assert len(results) == 1
    assert len(ytdlp.download_calls) == 1


def test_process_movie_adds_language_suffix_for_fallback(tmp_path: Path) -> None:
    folder_path = tmp_path / "Oldboy (2003)"
    folder = MovieFolder(path=folder_path, movie_name="Oldboy", year=2003, has_trailer=False)

    search_result = TrailerSearchResult(
        found=True,
        video_info=VideoInfo(title="Oldboy Trailer Deutsch", url="https://youtube.com/watch?v=de"),
        language="de",
    )

    ytdlp = FakeYtdlp()
    service = TrailerDownloadService(
        ytdlp_runner=ytdlp,
        scanner=FakeScanner([folder]),
        search_service=FakeSearchService([search_result]),
    )

    result = service.process_movie(folder, preferred_languages=("en", "de"), dry_run=True)

    assert result.success is True
    assert result.trailer_path is not None
    assert result.trailer_path.name.endswith("-trailer-de.mp4")
