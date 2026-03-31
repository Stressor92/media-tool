# tests/unit/test_jellyfin_client.py
from unittest.mock import MagicMock, patch

import pytest

from core.jellyfin.client import (
    JellyfinAuthError,
    JellyfinClient,
    JellyfinNotFoundError,
    JellyfinServerError,
)


@pytest.fixture()
def client() -> JellyfinClient:
    return JellyfinClient("http://localhost:8096", "test-key")


class TestJellyfinClient:
    def test_auth_headers_contain_token(self, client: JellyfinClient) -> None:
        headers = client._auth_headers()
        assert "test-key" in headers["Authorization"]
        assert "media-tool" in headers["Authorization"]

    def test_url_construction_with_leading_slash(self, client: JellyfinClient) -> None:
        assert client._url("/System/Info") == "http://localhost:8096/System/Info"

    def test_url_construction_without_leading_slash(self, client: JellyfinClient) -> None:
        assert client._url("Items") == "http://localhost:8096/Items"

    def test_base_url_trailing_slash_stripped(self) -> None:
        c = JellyfinClient("http://localhost:8096/", "key")
        assert c._url("/System/Info") == "http://localhost:8096/System/Info"

    def test_raise_for_401_raises_auth_error(self, client: JellyfinClient) -> None:
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        with pytest.raises(JellyfinAuthError):
            client._raise_for_status(mock_resp)

    def test_raise_for_403_raises_auth_error(self, client: JellyfinClient) -> None:
        mock_resp = MagicMock()
        mock_resp.status_code = 403
        with pytest.raises(JellyfinAuthError):
            client._raise_for_status(mock_resp)

    def test_raise_for_404_raises_not_found(self, client: JellyfinClient) -> None:
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_resp.url = "http://localhost/test"
        with pytest.raises(JellyfinNotFoundError):
            client._raise_for_status(mock_resp)

    def test_raise_for_500_raises_server_error(self, client: JellyfinClient) -> None:
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "Internal Server Error"
        with pytest.raises(JellyfinServerError):
            client._raise_for_status(mock_resp)

    def test_raise_for_200_does_not_raise(self, client: JellyfinClient) -> None:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status.return_value = None
        # Should not raise
        client._raise_for_status(mock_resp)

    def test_ping_returns_false_on_connection_error(self, client: JellyfinClient) -> None:
        with patch.object(client, "get", side_effect=ConnectionError("refused")):
            assert client.ping() is False

    def test_ping_returns_true_on_valid_response(self, client: JellyfinClient) -> None:
        with patch.object(client, "get", return_value={"Version": "10.9.0"}):
            assert client.ping() is True

    def test_ping_returns_false_on_empty_version(self, client: JellyfinClient) -> None:
        with patch.object(client, "get", return_value={"Version": ""}):
            assert client.ping() is False

    def test_session_lazily_initialised(self, client: JellyfinClient) -> None:
        assert client._session is None
        _ = client._get_session()
        assert client._session is not None

    def test_session_reused_on_second_call(self, client: JellyfinClient) -> None:
        s1 = client._get_session()
        s2 = client._get_session()
        assert s1 is s2
