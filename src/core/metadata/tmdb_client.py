from __future__ import annotations

import hashlib
import json
import logging
import time
from pathlib import Path
from typing import Any

from requests import Session
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

_TMDB_BASE = "https://api.themoviedb.org/3"
_IMAGE_BASE = "https://image.tmdb.org/t/p"
_CACHE_DIR = Path.home() / ".cache" / "media-tool" / "tmdb"
_CACHE_TTL_SECONDS = 7 * 24 * 3600


class TmdbAuthError(RuntimeError):
    pass


class TmdbRateLimitError(RuntimeError):
    pass


class TmdbClient:
    def __init__(
        self,
        api_key: str,
        language: str = "de-DE",
        fallback_language: str = "en-US",
        use_cache: bool = True,
        cache_dir: Path | None = None,
    ) -> None:
        self._api_key = api_key
        self._language = language
        self._fallback = fallback_language
        self._use_cache = use_cache
        self._cache_dir = cache_dir or _CACHE_DIR
        self._session: Session | None = None
        self._request_times: list[float] = []

        if self._use_cache:
            self._cache_dir.mkdir(parents=True, exist_ok=True)

    def _get_session(self) -> Session:
        if self._session is None:
            session = Session()
            retry = Retry(
                total=3,
                backoff_factor=1.0,
                status_forcelist={500, 502, 503, 504},
            )
            session.mount("https://", HTTPAdapter(max_retries=retry))
            self._session = session
        return self._session

    def _rate_limit(self) -> None:
        now = time.monotonic()
        self._request_times = [point for point in self._request_times if now - point < 10]
        if len(self._request_times) >= 38:
            sleep_seconds = 10 - (now - self._request_times[0]) + 0.1
            if sleep_seconds > 0:
                time.sleep(sleep_seconds)
        self._request_times.append(time.monotonic())

    def _cache_key(self, path: str, params: dict[str, Any]) -> str:
        raw = f"{path}|{json.dumps(params, sort_keys=True)}"
        return hashlib.md5(raw.encode("utf-8"), usedforsecurity=False).hexdigest()

    def _from_cache(self, key: str) -> dict[str, Any] | None:
        if not self._use_cache:
            return None
        cache_file = self._cache_dir / f"{key}.json"
        if not cache_file.exists():
            return None
        if (time.time() - cache_file.stat().st_mtime) >= _CACHE_TTL_SECONDS:
            return None

        try:
            parsed = json.loads(cache_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

        return parsed if isinstance(parsed, dict) else None

    def _to_cache(self, key: str, data: dict[str, Any]) -> None:
        if not self._use_cache:
            return
        try:
            cache_file = self._cache_dir / f"{key}.json"
            cache_file.write_text(json.dumps(data), encoding="utf-8")
        except OSError:
            logger.debug("Unable to write TMDB cache entry", exc_info=True)

    def get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        all_params: dict[str, Any] = {
            "api_key": self._api_key,
            "language": self._language,
            **(params or {}),
        }

        cache_key = self._cache_key(path, all_params)
        cached = self._from_cache(cache_key)
        if cached is not None:
            return cached

        self._rate_limit()
        response = self._get_session().get(
            f"{_TMDB_BASE}{path}",
            params=all_params,
            timeout=20,
        )

        if response.status_code == 401:
            raise TmdbAuthError("Invalid TMDB API key.")
        if response.status_code == 429:
            raise TmdbRateLimitError("TMDB rate limit reached.")
        response.raise_for_status()

        payload = response.json()
        if not isinstance(payload, dict):
            raise RuntimeError("Unexpected TMDB response type")

        self._to_cache(cache_key, payload)
        return payload

    def get_with_fallback(
        self,
        path: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        primary = self.get(path, params)

        if primary.get("overview") and primary.get("tagline"):
            return primary

        try:
            fallback_params = {**(params or {}), "language": self._fallback}
            fallback_payload = self.get(path, fallback_params)
            for field in ("overview", "tagline", "title"):
                if not primary.get(field) and fallback_payload.get(field):
                    primary[field] = fallback_payload[field]
        except Exception:
            logger.debug("TMDB fallback request failed", exc_info=True)

        return primary

    @staticmethod
    def image_url(path: str, size: str = "original") -> str:
        return f"{_IMAGE_BASE}/{size}{path}"
