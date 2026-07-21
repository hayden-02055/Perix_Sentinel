"""Golden-file characterization test for the Mistral collector (Astro-based).

Pins the current parse output against a saved real HTML snapshot.
``published_at`` is compared as a date-only string (YYYY-MM-DD) because Mistral
provides plain text dates ("June 23, 2026") that parse to midnight UTC — stable
across runs.
"""
from __future__ import annotations

import json

import pytest

from app.infrastructure.collectors.mistral_html_collector import (
    NEWS_URL,
    MistralHtmlCollector,
)
from tests.conftest import load_fixture


@pytest.mark.asyncio
async def test_mistral_collect_matches_golden(mock_http):
    mock_http(NEWS_URL, load_fixture("mistral_news.html"))
    expected = json.loads(load_fixture("mistral_news.golden.json"))

    items = await MistralHtmlCollector().collect()

    actual = [
        {
            "source": it.source,
            "title": it.title,
            "url": it.url,
            "tags": it.tags,
            "summary": it.summary,
            "published_at_date": it.published_at.date().isoformat(),
        }
        for it in items
    ]
    assert actual == expected


@pytest.mark.asyncio
async def test_mistral_collect_returns_nonempty(mock_http):
    mock_http(NEWS_URL, load_fixture("mistral_news.html"))
    items = await MistralHtmlCollector().collect()
    assert len(items) > 0


@pytest.mark.asyncio
async def test_mistral_collect_all_dates_aware_utc(mock_http):
    mock_http(NEWS_URL, load_fixture("mistral_news.html"))
    items = await MistralHtmlCollector().collect()
    for it in items:
        assert it.published_at.tzinfo is not None, f"naive date for {it.url}"
        assert it.published_at.utcoffset().total_seconds() == 0


@pytest.mark.asyncio
async def test_mistral_collect_all_have_mistral_tag(mock_http):
    mock_http(NEWS_URL, load_fixture("mistral_news.html"))
    items = await MistralHtmlCollector().collect()
    for it in items:
        assert "mistral" in it.tags
        assert it.source == "Mistral AI"


@pytest.mark.asyncio
async def test_mistral_collect_no_duplicate_urls(mock_http):
    mock_http(NEWS_URL, load_fixture("mistral_news.html"))
    items = await MistralHtmlCollector().collect()
    urls = [it.url for it in items]
    assert len(urls) == len(set(urls)), "duplicate URLs in Mistral output"
