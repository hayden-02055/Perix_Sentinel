"""Golden-file characterization test for the Anthropic collector.

Pins the current ``parse`` output against a saved real HTML snapshot. Runs with
no network. ``published_at`` is compared with ``tzinfo`` stripped so the test
stays green after R3 promotes dates to timezone-aware UTC (the instant is
unchanged; only the offset is added).
"""
from __future__ import annotations

import json

import pytest

from app.infrastructure.collectors.anthropic_html_collector import (
    NEWS_URL,
    AnthropicHtmlCollector,
)
from tests.conftest import load_fixture


@pytest.mark.asyncio
async def test_anthropic_collect_matches_golden(mock_http):
    mock_http(NEWS_URL, load_fixture("anthropic_news.html"))
    expected = json.loads(load_fixture("anthropic_news.golden.json"))

    items = await AnthropicHtmlCollector().collect()

    actual = [
        {
            "source": it.source,
            "title": it.title,
            "url": it.url,
            "summary": it.summary,
            "tags": it.tags,
            "published_at": it.published_at.replace(tzinfo=None).isoformat(),
        }
        for it in items
    ]
    assert actual == expected
