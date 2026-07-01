"""Golden-file characterization test for the Google Research RSS collector.

Pins the parser and filter output against a saved RSS XML snapshot (4 entries).
Entry 4 ("cloud economics") has no AI category and no AI keyword → filtered out.
Runs with no network: monkeypatches feedparser.parse to return the pre-parsed feed.
"""
from __future__ import annotations

import json

import feedparser
import pytest

from app.infrastructure.collectors.google_research_rss_collector import GoogleResearchRssCollector
from tests.conftest import load_fixture


@pytest.mark.asyncio
async def test_google_research_collect_matches_golden(monkeypatch):
    xml = load_fixture("google_research_feed.xml")
    parsed_feed = feedparser.parse(xml)
    monkeypatch.setattr(feedparser, "parse", lambda _url: parsed_feed)

    expected = json.loads(load_fixture("google_research_feed.golden.json"))

    items = await GoogleResearchRssCollector().collect()

    assert len(items) == 3, f"Expected 3 AI items (1 filtered out), got {len(items)}"

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
        assert a["published_at"] == e["published_at"].rstrip("Z").replace("+00:00", ""), f"[{i}] published_at"


@pytest.mark.asyncio
async def test_google_research_non_ai_entry_is_filtered(monkeypatch):
    """Entry 4 (cloud economics, tags: Algorithms & Theory / Data Management) must be excluded."""
    xml = load_fixture("google_research_feed.xml")
    parsed_feed = feedparser.parse(xml)
    monkeypatch.setattr(feedparser, "parse", lambda _url: parsed_feed)

    items = await GoogleResearchRssCollector().collect()

    titles = [it.title for it in items]
    assert all("cloud economics" not in t.lower() for t in titles), (
        "Non-AI 'cloud economics' entry should have been filtered out"
    )
