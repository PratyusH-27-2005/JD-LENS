"""The rate-limit key must be an address the client can't choose.

Regression test for a bypass found on the live deploy: with uvicorn trusting
X-Forwarded-For, sending a fake header gave a fresh limit on every request.
"""

import pytest
from starlette.requests import Request

from app.config import Settings
from app.ratelimit import client_ip


def _request(headers: dict[str, str], peer: str = "10.0.0.7") -> Request:
    return Request(
        {
            "type": "http",
            "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
            "client": (peer, 5555),
        }
    )


@pytest.fixture
def behind_cloudflare(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("app.ratelimit.get_settings", lambda: Settings(trust_cf_connecting_ip=True))


@pytest.fixture
def direct(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "app.ratelimit.get_settings", lambda: Settings(trust_cf_connecting_ip=False)
    )


def test_x_forwarded_for_is_never_trusted(direct):
    assert client_ip(_request({"x-forwarded-for": "1.2.3.4"})) == "10.0.0.7"


def test_x_forwarded_for_is_ignored_behind_cloudflare_too(behind_cloudflare):
    request = _request({"x-forwarded-for": "1.2.3.4", "cf-connecting-ip": "203.0.113.9"})
    assert client_ip(request) == "203.0.113.9"


def test_cf_connecting_ip_only_trusted_when_configured(direct):
    assert client_ip(_request({"cf-connecting-ip": "203.0.113.9"})) == "10.0.0.7"


def test_falls_back_to_socket_address_without_the_header(behind_cloudflare):
    assert client_ip(_request({})) == "10.0.0.7"
