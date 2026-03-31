# src/core/jellyfin/client.py
from __future__ import annotations

import logging
from typing import Any, Optional
from urllib.parse import urljoin

import requests
from requests import Response, Session
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = 30
_MAX_RETRIES = 3


class JellyfinAuthError(Exception):
    """401 / 403 — invalid or expired API key."""


class JellyfinNotFoundError(Exception):
    """404 — item or endpoint not found."""


class JellyfinServerError(Exception):
    """5xx — server-side error."""


class JellyfinClient:
    """
    Thin HTTP client for the Jellyfin REST API.

    - Automatic retry logic (3×, exponential backoff)
    - Structured exceptions instead of raw HTTP codes
    - Lazy session initialisation
    """

    def __init__(
        self,
        base_url: str,
        api_key: str,
        timeout: int = _DEFAULT_TIMEOUT,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout = timeout
        self._session: Optional[Session] = None

    def _get_session(self) -> Session:
        if self._session is None:
            self._session = self._build_session()
        return self._session

    def _build_session(self) -> Session:
        session = Session()
        retry = Retry(
            total=_MAX_RETRIES,
            backoff_factor=0.5,
            status_forcelist={500, 502, 503, 504},
            allowed_methods={"GET", "POST", "DELETE"},
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        session.headers.update(self._auth_headers())
        return session

    def _auth_headers(self) -> dict[str, str]:
        return {
            "Authorization": (
                f'MediaBrowser Client="media-tool", '
                f'Device="CLI", '
                f'DeviceId="media-tool-cli-v1", '
                f'Version="1.0", '
                f'Token="{self._api_key}"'
            ),
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _url(self, path: str) -> str:
        return urljoin(self._base_url + "/", path.lstrip("/"))

    def _raise_for_status(self, response: Response) -> None:
        if response.status_code == 401:
            raise JellyfinAuthError("Invalid API key or missing permission.")
        if response.status_code == 403:
            raise JellyfinAuthError("Access denied (403).")
        if response.status_code == 404:
            raise JellyfinNotFoundError(f"Resource not found: {response.url}")
        if response.status_code >= 500:
            raise JellyfinServerError(
                f"Server error {response.status_code}: {response.text[:200]}"
            )
        response.raise_for_status()

    def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        url = self._url(path)
        logger.debug("GET %s params=%s", url, params)
        resp = self._get_session().get(url, params=params, timeout=self._timeout)
        self._raise_for_status(resp)
        return resp.json() if resp.content else {}

    def post(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
    ) -> Any:
        url = self._url(path)
        logger.debug("POST %s", url)
        resp = self._get_session().post(
            url, params=params, json=body, timeout=self._timeout
        )
        self._raise_for_status(resp)
        return resp.json() if resp.content else {}

    def ping(self) -> bool:
        """Returns True if the server is reachable and the key is valid."""
        try:
            info = self.get("/System/Info")
            return bool(info.get("Version"))
        except Exception as exc:
            logger.warning("Jellyfin not reachable: %s", exc)
            return False
