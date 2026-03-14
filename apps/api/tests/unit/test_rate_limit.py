"""Unit tests for rate limiting components."""

import json
from unittest.mock import MagicMock

import pytest
from fastapi import Request
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

from coyo.middleware import rate_limit_handler
from coyo.rate_limit import _get_user_id_or_ip


# ---------------------------------------------------------------------------
# _get_user_id_or_ip
# ---------------------------------------------------------------------------


class TestGetUserIdOrIp:
    """Tests for the _get_user_id_or_ip key function."""

    @pytest.mark.unit
    def test_returns_user_id_when_user_is_authenticated(self):
        request = MagicMock(spec=Request)
        user = MagicMock()
        user.id = "user-abc-123"
        request.state.current_user = user

        result = _get_user_id_or_ip(request)

        assert result == "user-abc-123"

    @pytest.mark.unit
    def test_returns_user_id_as_string_for_uuid(self):
        import uuid

        request = MagicMock(spec=Request)
        user = MagicMock()
        user_uuid = uuid.uuid4()
        user.id = user_uuid
        request.state.current_user = user

        result = _get_user_id_or_ip(request)

        assert result == str(user_uuid)

    @pytest.mark.unit
    def test_returns_ip_when_no_current_user(self):
        request = MagicMock(spec=Request)
        request.state.current_user = None
        request.client.host = "192.168.1.100"

        result = _get_user_id_or_ip(request)

        assert result == "192.168.1.100"

    @pytest.mark.unit
    def test_returns_ip_when_state_has_no_current_user_attribute(self):
        request = MagicMock(spec=Request)
        del request.state.current_user
        request.client.host = "10.0.0.1"

        result = _get_user_id_or_ip(request)

        assert result == "10.0.0.1"

    @pytest.mark.unit
    def test_returns_ip_when_request_has_no_state(self):
        """Handles the edge case where request.state itself is missing."""
        request = MagicMock(spec=Request)
        type(request).state = property(lambda self: None)
        request.client.host = "172.16.0.1"

        result = _get_user_id_or_ip(request)

        assert result == "172.16.0.1"


# ---------------------------------------------------------------------------
# rate_limit_handler
# ---------------------------------------------------------------------------


class TestRateLimitHandler:
    """Tests for the rate_limit_handler middleware function."""

    @staticmethod
    def _make_rate_limit_exc(detail_str: str = "10 per 1 minute") -> RateLimitExceeded:
        """Create a RateLimitExceeded with a controlled detail string."""
        limit_mock = MagicMock()
        limit_mock.error_message = None
        exc = RateLimitExceeded(limit_mock)
        exc.detail = detail_str
        return exc

    @pytest.mark.unit
    async def test_returns_429_status(self):
        request = MagicMock(spec=Request)
        request.url = "http://test/api/conversations"
        exc = self._make_rate_limit_exc("1 per 1 minute")

        response = await rate_limit_handler(request, exc)

        assert isinstance(response, JSONResponse)
        assert response.status_code == 429

    @pytest.mark.unit
    async def test_returns_error_envelope(self):
        request = MagicMock(spec=Request)
        request.url = "http://test/api/auth/session"
        exc = self._make_rate_limit_exc("10 per 1 minute")

        response = await rate_limit_handler(request, exc)

        data = json.loads(response.body.decode())
        assert data["error"]["code"] == "RATE_LIMIT_EXCEEDED"
        assert data["error"]["message"] == "Rate limit exceeded"

    @pytest.mark.unit
    async def test_includes_rfc_compliant_retry_after_header(self):
        request = MagicMock(spec=Request)
        request.url = "http://test/api/history"
        exc = self._make_rate_limit_exc("30 per 1 minute")

        response = await rate_limit_handler(request, exc)

        assert response.headers["retry-after"] == "60"

    @pytest.mark.unit
    async def test_error_envelope_has_no_extra_fields(self):
        request = MagicMock(spec=Request)
        request.url = "http://test/api/conversations"
        exc = self._make_rate_limit_exc("5 per 1 minute")

        response = await rate_limit_handler(request, exc)

        data = json.loads(response.body.decode())
        assert set(data.keys()) == {"error"}
        assert set(data["error"].keys()) == {"code", "message"}
