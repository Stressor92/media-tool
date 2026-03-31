from __future__ import annotations

from pathlib import Path

from core.video.movie_folder_scanner import MovieFolderScanner
from core.video.trailer_downloader import TrailerDownloadService
from core.video.trailer_search import TrailerSearchService
from utils.ytdlp_runner import DownloadResult, VideoInfo


class FakeYtdlpRunner:
    def search(self, query: str, max_results: int = 5, timeout_seconds: int = 30) -> list[VideoInfo]:
        del max_results, timeout_seconds
        if "Movie Two" in query:
            return []
        return [VideoInfo(title="Movie One Official Trailer", url="https://youtube.com/watch?v=movie1")]

    def download(self, url: str, output_path: Path, timeout_seconds: int = 600) -> DownloadResult:
        del timeout_seconds
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(url.encode("utf-8"))
        return DownloadResult(success=True, file_path=output_path)


def test_trailer_workflow_dry_run(tmp_path: Path) -> None:
    movie_one = tmp_path / "Movie One (2020)"
    movie_one.mkdir(parents=True)
    (movie_one / "Movie One (2020).mkv").write_bytes(b"video")

    movie_two = tmp_path / "Movie Two (2021)"
    movie_two.mkdir(parents=True)
    (movie_two / "Movie Two (2021).mkv").write_bytes(b"video")

    runner = FakeYtdlpRunner()
    search = TrailerSearchService(runner)
    scanner = MovieFolderScanner()
    service = TrailerDownloadService(ytdlp_runner=runner, search_service=search, scanner=scanner)

    results = service.process_library(
        library_path=tmp_path,
        preferred_languages=("en", "de"),
        dry_run=True,
        skip_existing=True,
    )

    assert len(results) == 2
    success_results = [result for result in results if result.success]
    failed_results = [result for result in results if not result.success]

    assert len(success_results) == 1
    assert len(failed_results) == 1
    assert success_results[0].trailer_path is not None
    assert success_results[0].trailer_path.name.endswith("-trailer.mp4")
