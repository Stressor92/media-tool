# tests/unit/test_audit_checks.py
from __future__ import annotations

from pathlib import Path

import pytest

from core.audit.checks.audio_checks import MissingDeAudioCheck, UnlabeledAudioCheck
from core.audit.checks.file_quality_checks import (
    BrokenFileCheck,
    SuspiciousFileSizeCheck,
    WrongContainerCheck,
)
from core.audit.checks.naming_checks import (
    BadMovieNamingCheck,
    DuplicateMovieCheck,
    EmptyFolderCheck,
    FileInRootCheck,
    NameTooLongCheck,
    SpecialCharsCheck,
)
from core.audit.checks.series_checks import BadEpisodeNamingCheck, EpisodeGapCheck
from core.audit.checks.subtitle_checks import (
    MissingDeSubtitleCheck,
    MissingEnSubtitleCheck,
    NoSubtitlesAtAllCheck,
)
from core.audit.models import CheckSeverity, FindingKind


# ── Helpers ──────────────────────────────────────────────────────────────────


def _probe_with_subs(*langs: str) -> dict:
    return {
        "streams": [
            {"codec_type": "subtitle", "tags": {"language": lang}} for lang in langs
        ]
    }


def _probe_with_audio(*langs: str) -> dict:
    return {
        "streams": [
            {"codec_type": "audio", "tags": {"language": lang}} for lang in langs
        ]
    }


def _probe_empty() -> dict:
    return {"streams": []}


# ── Subtitle Checks ───────────────────────────────────────────────────────────


class TestMissingDeSubtitleCheck:
    def test_missing_de_detected(self, tmp_path: Path) -> None:
        f = tmp_path / "Film (2020).mkv"
        f.touch()
        check = MissingDeSubtitleCheck()
        findings = check.run([f], {f: _probe_with_subs("en")})
        assert len(findings) == 1
        assert findings[0].kind == FindingKind.MISSING_DE_SUBTITLE

    def test_no_finding_when_de_present(self, tmp_path: Path) -> None:
        f = tmp_path / "Film (2020).mkv"
        f.touch()
        check = MissingDeSubtitleCheck()
        findings = check.run([f], {f: _probe_with_subs("ger", "en")})
        assert findings == []

    def test_de_code_variants_accepted(self, tmp_path: Path) -> None:
        for lang in ("deu", "de", "german"):
            f = tmp_path / f"Film_{lang}.mkv"
            f.touch()
            findings = MissingDeSubtitleCheck().run([f], {f: _probe_with_subs(lang)})
            assert findings == [], f"Expected no finding for language code '{lang}'"

    def test_suggested_command_included(self, tmp_path: Path) -> None:
        f = tmp_path / "Film (2020).mkv"
        f.touch()
        findings = MissingDeSubtitleCheck().run([f], {f: _probe_empty()})
        assert findings[0].suggested_command is not None
        assert "subtitle download" in findings[0].suggested_command

    def test_severity_is_high(self, tmp_path: Path) -> None:
        f = tmp_path / "Film (2020).mkv"
        f.touch()
        findings = MissingDeSubtitleCheck().run([f], {f: _probe_empty()})
        assert findings[0].severity == CheckSeverity.HIGH


class TestMissingEnSubtitleCheck:
    def test_missing_en_detected(self, tmp_path: Path) -> None:
        f = tmp_path / "Film (2020).mkv"
        f.touch()
        findings = MissingEnSubtitleCheck().run([f], {f: _probe_with_subs("deu")})
        assert len(findings) == 1
        assert findings[0].kind == FindingKind.MISSING_EN_SUBTITLE

    def test_no_finding_when_en_present(self, tmp_path: Path) -> None:
        f = tmp_path / "Film (2020).mkv"
        f.touch()
        findings = MissingEnSubtitleCheck().run([f], {f: _probe_with_subs("en")})
        assert findings == []


class TestNoSubtitlesAtAllCheck:
    def test_no_subs_detected(self, tmp_path: Path) -> None:
        f = tmp_path / "Film (2020).mkv"
        f.touch()
        findings = NoSubtitlesAtAllCheck().run([f], {f: _probe_empty()})
        assert len(findings) == 1
        assert findings[0].kind == FindingKind.NO_SUBTITLES

    def test_no_finding_when_subs_present(self, tmp_path: Path) -> None:
        f = tmp_path / "Film (2020).mkv"
        f.touch()
        findings = NoSubtitlesAtAllCheck().run([f], {f: _probe_with_subs("en")})
        assert findings == []


# ── Audio Checks ──────────────────────────────────────────────────────────────


class TestUnlabeledAudioCheck:
    def test_unlabeled_detected(self, tmp_path: Path) -> None:
        f = tmp_path / "Film (2020).mkv"
        f.touch()
        probe = {
            "streams": [{"codec_type": "audio", "tags": {"language": "und"}}]
        }
        findings = UnlabeledAudioCheck().run([f], {f: probe})
        assert len(findings) == 1
        assert findings[0].kind == FindingKind.UNLABELED_AUDIO

    def test_no_finding_when_labeled(self, tmp_path: Path) -> None:
        f = tmp_path / "Film (2020).mkv"
        f.touch()
        findings = UnlabeledAudioCheck().run([f], {f: _probe_with_audio("deu")})
        assert findings == []

    def test_empty_language_treated_as_unlabeled(self, tmp_path: Path) -> None:
        f = tmp_path / "Film (2020).mkv"
        f.touch()
        probe = {"streams": [{"codec_type": "audio", "tags": {"language": ""}}]}
        findings = UnlabeledAudioCheck().run([f], {f: probe})
        assert len(findings) == 1


class TestMissingDeAudioCheck:
    def test_en_only_detected(self, tmp_path: Path) -> None:
        f = tmp_path / "Film (2020).mkv"
        f.touch()
        findings = MissingDeAudioCheck().run([f], {f: _probe_with_audio("en")})
        assert len(findings) == 1
        assert findings[0].kind == FindingKind.MISSING_DE_AUDIO

    def test_no_finding_with_de_audio(self, tmp_path: Path) -> None:
        f = tmp_path / "Film (2020).mkv"
        f.touch()
        findings = MissingDeAudioCheck().run([f], {f: _probe_with_audio("en", "deu")})
        assert findings == []

    def test_no_finding_without_any_audio(self, tmp_path: Path) -> None:
        f = tmp_path / "Film (2020).mkv"
        f.touch()
        findings = MissingDeAudioCheck().run([f], {f: _probe_empty()})
        assert findings == []


# ── Naming Checks ─────────────────────────────────────────────────────────────


class TestBadMovieNamingCheck:
    def test_bad_naming_detected(self, tmp_path: Path) -> None:
        f = tmp_path / "film_without_year.mkv"
        f.touch()
        findings = BadMovieNamingCheck().run([f], {})
        assert len(findings) == 1
        assert findings[0].kind == FindingKind.BAD_MOVIE_NAMING

    def test_correct_naming_passes(self, tmp_path: Path) -> None:
        f = tmp_path / "Inception (2010).mkv"
        f.touch()
        findings = BadMovieNamingCheck().run([f], {})
        assert findings == []

    def test_series_files_skipped(self, tmp_path: Path) -> None:
        series_dir = tmp_path / "Breaking Bad" / "Season 01"
        series_dir.mkdir(parents=True)
        f = series_dir / "badly_named_episode.mkv"
        f.touch()
        findings = BadMovieNamingCheck().run([f], {})
        assert findings == []


class TestDuplicateMovieCheck:
    def test_duplicate_detection(self, tmp_path: Path) -> None:
        f1 = tmp_path / "Inception (2010).mkv"
        f2 = tmp_path / "Inception (2010) [DE].mkv"
        f1.touch()
        f2.touch()
        findings = DuplicateMovieCheck().run([f1, f2], {})
        assert len(findings) == 2
        assert all(f.kind == FindingKind.DUPLICATE_MOVIE for f in findings)

    def test_no_duplicate_unique_films(self, tmp_path: Path) -> None:
        f1 = tmp_path / "Inception (2010).mkv"
        f2 = tmp_path / "Dune (2021).mkv"
        f1.touch()
        f2.touch()
        findings = DuplicateMovieCheck().run([f1, f2], {})
        assert findings == []


class TestFileInRootCheck:
    def test_file_in_root_detected(self, tmp_path: Path) -> None:
        f = tmp_path / "Film.mkv"
        f.touch()
        findings = FileInRootCheck(tmp_path).run([f], {})
        assert len(findings) == 1
        assert findings[0].kind == FindingKind.FILE_IN_ROOT

    def test_subdirectory_file_passes(self, tmp_path: Path) -> None:
        sub = tmp_path / "Film (2020)"
        sub.mkdir()
        f = sub / "Film (2020).mkv"
        f.touch()
        findings = FileInRootCheck(tmp_path).run([f], {})
        assert findings == []


class TestEmptyFolderCheck:
    def test_empty_folder_detected(self, tmp_path: Path) -> None:
        empty = tmp_path / "EmptyFolder"
        empty.mkdir()
        findings = EmptyFolderCheck(tmp_path).run([], {})
        assert len(findings) == 1
        assert findings[0].kind == FindingKind.EMPTY_FOLDER

    def test_non_empty_folder_passes(self, tmp_path: Path) -> None:
        sub = tmp_path / "NotEmpty"
        sub.mkdir()
        (sub / "file.mkv").touch()
        findings = EmptyFolderCheck(tmp_path).run([], {})
        assert findings == []


class TestSpecialCharsCheck:
    def test_special_char_detected(self, tmp_path: Path) -> None:
        # The check only reads .name; patch via unittest.mock
        from unittest.mock import MagicMock

        fake = MagicMock(spec=Path)
        fake.name = "Film: Untertitel (2020).mkv"
        findings = SpecialCharsCheck().run([fake], {})
        assert len(findings) == 1
        assert findings[0].kind == FindingKind.SPECIAL_CHARS

    def test_clean_name_passes(self, tmp_path: Path) -> None:
        f = tmp_path / "Inception (2010).mkv"
        f.touch()
        findings = SpecialCharsCheck().run([f], {})
        assert findings == []


class TestNameTooLongCheck:
    def test_long_name_detected(self, tmp_path: Path) -> None:
        from unittest.mock import MagicMock

        long_name = "A" * 201 + ".mkv"
        fake = MagicMock(spec=Path)
        fake.name = long_name
        findings = NameTooLongCheck().run([fake], {})
        assert len(findings) == 1
        assert findings[0].kind == FindingKind.NAME_TOO_LONG

    def test_short_name_passes(self, tmp_path: Path) -> None:
        f = tmp_path / "Inception (2010).mkv"
        f.touch()
        findings = NameTooLongCheck().run([f], {})
        assert findings == []


# ── Series Checks ─────────────────────────────────────────────────────────────


class TestEpisodeGapCheck:
    def test_episode_gap_detected(self, tmp_path: Path) -> None:
        series_dir = tmp_path / "My Show" / "Season 01"
        series_dir.mkdir(parents=True)
        files = [
            series_dir / "My.Show.S01E01.mkv",
            series_dir / "My.Show.S01E02.mkv",
            # E03 fehlt absichtlich
            series_dir / "My.Show.S01E04.mkv",
        ]
        for f in files:
            f.touch()
        findings = EpisodeGapCheck().run(files, {})
        assert len(findings) == 1
        assert findings[0].details["missing_episodes"] == [3]

    def test_no_gap_no_finding(self, tmp_path: Path) -> None:
        series_dir = tmp_path / "My Show" / "Season 01"
        series_dir.mkdir(parents=True)
        files = [series_dir / f"My.Show.S01E0{i}.mkv" for i in range(1, 5)]
        for f in files:
            f.touch()
        findings = EpisodeGapCheck().run(files, {})
        assert findings == []

    def test_non_episode_files_ignored(self, tmp_path: Path) -> None:
        f = tmp_path / "movie_without_episode_pattern.mkv"
        f.touch()
        findings = EpisodeGapCheck().run([f], {})
        assert findings == []


class TestBadEpisodeNamingCheck:
    def test_bad_naming_in_season_folder(self, tmp_path: Path) -> None:
        series_dir = tmp_path / "My Show" / "Season 01"
        series_dir.mkdir(parents=True)
        f = series_dir / "episode_without_pattern.mkv"
        f.touch()
        findings = BadEpisodeNamingCheck().run([f], {})
        assert len(findings) == 1
        assert findings[0].kind == FindingKind.BAD_EPISODE_NAMING

    def test_correct_pattern_passes(self, tmp_path: Path) -> None:
        series_dir = tmp_path / "My Show" / "Season 01"
        series_dir.mkdir(parents=True)
        f = series_dir / "My.Show.S01E01.mkv"
        f.touch()
        findings = BadEpisodeNamingCheck().run([f], {})
        assert findings == []


# ── File Quality Checks ───────────────────────────────────────────────────────


class TestBrokenFileCheck:
    def test_missing_probe_detected(self, tmp_path: Path) -> None:
        f = tmp_path / "broken.mkv"
        f.touch()
        # No entry in probes → treated as broken
        findings = BrokenFileCheck().run([f], {})
        assert len(findings) == 1
        assert findings[0].kind == FindingKind.BROKEN_FILE
        assert findings[0].severity == CheckSeverity.CRITICAL

    def test_empty_file_detected(self, tmp_path: Path) -> None:
        f = tmp_path / "empty.mkv"
        f.touch()
        findings = BrokenFileCheck().run([f], {f: {"streams": []}})
        assert len(findings) == 1

    def test_valid_probe_passes(self, tmp_path: Path) -> None:
        f = tmp_path / "good.mkv"
        # Write some bytes so st_size > 0
        f.write_bytes(b"\x00" * 1024)
        findings = BrokenFileCheck().run([f], {f: {"streams": []}})
        assert findings == []


class TestWrongContainerCheck:
    def test_mp4_detected(self, tmp_path: Path) -> None:
        f = tmp_path / "Film (2020).mp4"
        f.touch()
        findings = WrongContainerCheck().run([f], {})
        assert len(findings) == 1
        assert findings[0].kind == FindingKind.WRONG_CONTAINER

    def test_mkv_passes(self, tmp_path: Path) -> None:
        f = tmp_path / "Film (2020).mkv"
        f.touch()
        findings = WrongContainerCheck().run([f], {})
        assert findings == []


class TestSuspiciousFileSizeCheck:
    def test_small_file_detected(self, tmp_path: Path) -> None:
        f = tmp_path / "tiny.mkv"
        f.write_bytes(b"\x00" * 1024)  # 1 KB
        findings = SuspiciousFileSizeCheck().run([f], {})
        assert len(findings) == 1
        assert findings[0].kind == FindingKind.SUSPICIOUS_SIZE

    def test_large_file_passes(self, tmp_path: Path) -> None:
        f = tmp_path / "Film (2020).mkv"
        # Write 200 MB worth of zeros (sparse on most filesystems)
        f.write_bytes(b"\x00" * (200 * 1024 * 1024))
        findings = SuspiciousFileSizeCheck().run([f], {})
        assert findings == []
