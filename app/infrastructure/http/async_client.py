"""Centralised async HTTP helpers (R1/R2).

All outbound HTTP calls from collectors should go through these helpers so that
timeout, User-Agent, follow-redirects, and retry policy live in one place.
"""
from __future__ import annotations

import asyncio
import logging

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

_TIMEOUT = 20.0
_HEADERS = {"User-Agent": "Mozilla/5.0"}
_MAX_ATTEMPTS = 3
_RETRY_DELAYS = (1.0, 3.0)  # seconds between attempt 1→2 and 2→3


async def fetch_html(url: str) -> BeautifulSoup:
    """GET *url* and return a parsed BeautifulSoup tree.

    Retries up to _MAX_ATTEMPTS times on transient errors.
    Raises the last httpx exception if all attempts fail.
    """
    response = await _get(url)
    return BeautifulSoup(response.text, "html.parser")


async def fetch_json(url: str) -> dict:
    """GET *url* and return the parsed JSON body as a dict."""
    response = await _get(url)
    return response.json()


async def _get(url: str) -> httpx.Response:
    last_exc: Exception | None = None

    async with httpx.AsyncClient(
        follow_redirects=True,
        timeout=_TIMEOUT,
        headers=_HEADERS,
    ) as client:
        for attempt, delay in enumerate((*_RETRY_DELAYS, None), start=1):
            try:
                response = await client.get(url)
                response.raise_for_status()
                return response
            except (httpx.HTTPStatusError, httpx.TransportError) as exc:
                last_exc = exc
                logger.warning(
                    "HTTP attempt %d/%d failed for %s: %s",
                    attempt, _MAX_ATTEMPTS, url, exc,
                )
                if delay is not None:
                    await asyncio.sleep(delay)

    raise last_exc  # type: ignore[misc]
