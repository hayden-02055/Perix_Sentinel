"""Golden-file characterization test for the Hacker News collector.

Mocks two tiers of HN Firebase API calls via ``mock_http`` (URL-keyed routing,
same fixture used by the HTML/JSON collectors): topstories ID list, then one
item fetch per ID. Covers the filter matrix: AI-related w/ url, AI-related
self-post (url fallback to discussion link), non-AI story (filtered out),
and a non-story type (filtered out even though its title mentions "AI").
"""
from __future__ import annotations

import json

import pytest

from app.infrastructure.collectors.hackernews_api_collector import (
    TOPSTORIES_URL,
    HackerNewsApiCollector,
)
from tests.conftest import load_fixture

_ITEM_IDS = (101, 102, 103, 104)


def _item_url(item_id: int) -> str:
    return f"https://hacker-news.firebaseio.com/v0/item/{item_id}.json"


@pytest.mark.asyncio
async def test_hackernews_collect_matches_golden(mock_http):
    mock_http(TOPSTORIES_URL, load_fixture("hackernews_topstories.json"))
    for item_id in _ITEM_IDS:
        mock_http(_item_url(item_id), load_fixture(f"hackernews_item_{item_id}.json"))

    expected = json.loads(load_fixture("hackernews.golden.json"))

    items = await HackerNewsApiCollector().collect()

    actual = [
        {
            "source": it.source,
            "title": it.title,
            "url": it.url,
            "published_at": it.published_at.replace(tzinfo=None).isoformat(),
            "summary": it.summary,
            "tags": it.tags,
            "metadata": it.metadata,
        }
        for it in items
    ]

    assert actual == expected
