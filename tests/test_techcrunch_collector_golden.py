"""Golden-file characterization test for the TechCrunch RSS collector.

Pins the parser output against a saved RSS XML snapshot (3 entries).
Runs with no network: monkeypatches feedparser.parse to return the pre-parsed feed.
``published_at`` is compared as-is (aware UTC) via isoformat.
"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import feedparser
import pytest

from app.application.use_cases.collect_trends import CollectTrendsUseCase
from app.infrastructure.collectors.techcrunch_rss_collector import TechCrunchRssCollector
from tests.conftest import load_fixture


@pytest.mark.asyncio
async def test_techcrunch_collect_matches_golden(monkeypatch):
    xml = load_fixture("techcrunch_feed.xml")
    parsed_feed = feedparser.parse(xml)
    monkeypatch.setattr(feedparser, "parse", lambda _url: parsed_feed)

    expected = json.loads(load_fixture("techcrunch_feed.golden.json"))

    items = await TechCrunchRssCollector().collect()

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

    assert len(actual) == len(expected), f"count mismatch: {len(actual)} vs {len(expected)}"

    for i, (a, e) in enumerate(zip(actual, expected)):
        assert a["source"] == e["source"], f"[{i}] source"
        assert a["title"] == e["title"], f"[{i}] title"
        assert a["url"] == e["url"], f"[{i}] url"
        assert a["summary"] == e["summary"], f"[{i}] summary"
        assert a["tags"] == e["tags"], f"[{i}] tags"
        assert a["metadata"] == e["metadata"], f"[{i}] metadata"
        assert a["metadata"]["function"] == "coverage", f"[{i}] function must be coverage"
        assert a["published_at"] == e["published_at"].rstrip("Z"), f"[{i}] published_at"


@pytest.mark.asyncio
async def test_coverage_use_case_never_briefs(monkeypatch):
    """publisher=None 배선 시 브리핑이 0건임을 보장한다."""
    xml = load_fixture("techcrunch_feed.xml")
    parsed_feed = feedparser.parse(xml)
    monkeypatch.setattr(feedparser, "parse", lambda _url: parsed_feed)

    mock_repo = MagicMock()
    mock_repo.exists_by_hash = AsyncMock(return_value=False)
    mock_repo.save = AsyncMock(return_value=1)
    mock_repo.mark_briefed = AsyncMock()

    use_case = CollectTrendsUseCase(
        collector=TechCrunchRssCollector(),
        repository=mock_repo,
        publisher=None,
    )
    result = await use_case.execute()

    assert result["briefed"] == 0
