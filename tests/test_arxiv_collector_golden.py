"""Golden-file characterization test for the arXiv collector.

Pins the parser output against a saved real Atom XML snapshot (3 entries).
Runs with no network: monkeypatches feedparser.parse to return the pre-parsed feed.
``published_at`` is compared as-is (aware UTC) via isoformat.
"""
from __future__ import annotations

import json

import feedparser
import pytest

from app.infrastructure.collectors.arxiv_api_collector import ArxivApiCollector
from tests.conftest import load_fixture


@pytest.mark.asyncio
async def test_arxiv_collect_matches_golden(monkeypatch):
    xml = load_fixture("arxiv_feed.xml")
    parsed_feed = feedparser.parse(xml)
    monkeypatch.setattr(feedparser, "parse", lambda _url: parsed_feed)

    expected = json.loads(load_fixture("arxiv_feed.golden.json"))

    items = await ArxivApiCollector().collect()

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
        assert a["published_at"] == e["published_at"].rstrip("Z"), f"[{i}] published_at"
