"""Shared test fixtures.

The HTTP mock patches ``httpx.AsyncClient`` at the ``httpx`` module level so it
keeps working regardless of *where* the client is instantiated. Today each
collector builds its own ``httpx.AsyncClient``; after the P1/P2 refactor they
will go through ``infrastructure/http/async_client``. Both paths resolve
``httpx.AsyncClient`` from the same module object, so these characterization
tests survive the refactor without edits.
"""
from __future__ import annotations

from pathlib import Path

import httpx
import pytest

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


class _FakeResponse:
    def __init__(self, text: str, status_code: int = 200) -> None:
        self.text = text
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                f"status {self.status_code}",
                request=None,  # type: ignore[arg-type]
                response=None,  # type: ignore[arg-type]
            )

    def json(self):
        import json

        return json.loads(self.text)


class _FakeAsyncClient:
    """Drop-in for ``httpx.AsyncClient`` that serves canned responses by URL."""

    routes: dict[str, _FakeResponse] = {}

    def __init__(self, *args, **kwargs) -> None:  # noqa: D401 - signature parity
        pass

    async def __aenter__(self) -> "_FakeAsyncClient":
        return self

    async def __aexit__(self, *exc) -> bool:
        return False

    async def get(self, url: str, *args, **kwargs) -> _FakeResponse:
        if url not in self.routes:
            raise AssertionError(f"Unexpected HTTP GET to {url!r}")
        return self.routes[url]


@pytest.fixture
def mock_http(monkeypatch):
    """Return a registrar: ``register(url, body, status=200)``.

    Patches ``httpx.AsyncClient`` so any collector hitting ``url`` receives the
    registered body without touching the network.
    """
    routes: dict[str, _FakeResponse] = {}

    class _Client(_FakeAsyncClient):
        pass

    _Client.routes = routes
    monkeypatch.setattr(httpx, "AsyncClient", _Client)

    def register(url: str, body: str, status: int = 200) -> None:
        routes[url] = _FakeResponse(body, status)

    return register
