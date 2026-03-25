"""Unit tests for URL validation helpers."""

from utils.url_validator import classify_platform, is_valid_url


def test_is_valid_url_accepts_https() -> None:
    assert is_valid_url("https://www.youtube.com/watch?v=abc")


def test_is_valid_url_rejects_non_url() -> None:
    assert not is_valid_url("not-a-url")


def test_classify_platform_youtube() -> None:
    assert classify_platform("https://youtu.be/abc") == "youtube"


def test_classify_platform_unknown() -> None:
    assert classify_platform("https://example.com/resource") == "unknown"
