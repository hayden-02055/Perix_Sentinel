"""Golden-file characterization test for HuggingFaceApiCollector.

Verifies region derivation across 4 cases:
  [0] deepseek-ai/DeepSeek-V4      → region=cn  (1st signal: org handle)
  [1] bartowski/Qwen2.5-GGUF       → region=cn  (2nd signal: model-id substring)
  [2] meta-llama/Llama-4           → region=us  (1st signal: org handle)
  [3] randomuser/some-model        → region=global (fallback)

Runs with no network: mock_http fixture patches httpx.AsyncClient.
"""
from __future__ import annotations

import json

import pytest

from app.infrastructure.collectors.huggingface_api_collector import (
    HF_TRENDING_URL,
    HuggingFaceApiCollector,
)
from tests.conftest import load_fixture


@pytest.mark.asyncio
async def test_huggingface_collect_matches_golden(mock_http):
    mock_http(HF_TRENDING_URL, load_fixture("huggingface_trending.json"))
    expected = json.loads(load_fixture("huggingface_trending.golden.json"))

    items = await HuggingFaceApiCollector().collect()

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
        assert a["published_at"] == e["published_at"].replace("+00:00", "").rstrip("Z"), f"[{i}] published_at"


@pytest.mark.asyncio
async def test_region_cn_via_org_handle(mock_http):
    """deepseek-ai author → region=cn via 1st-signal org lookup."""
    mock_http(HF_TRENDING_URL, load_fixture("huggingface_trending.json"))
    items = await HuggingFaceApiCollector().collect()
    deepseek = next(it for it in items if "deepseek-ai" in it.title)
    assert deepseek.metadata["region"] == "cn"


@pytest.mark.asyncio
async def test_region_cn_via_model_substring(mock_http):
    """bartowski/Qwen2.5-GGUF: org unknown, but 'qwen' in model_id → region=cn."""
    mock_http(HF_TRENDING_URL, load_fixture("huggingface_trending.json"))
    items = await HuggingFaceApiCollector().collect()
    reupload = next(it for it in items if "bartowski" in it.title)
    assert reupload.metadata["region"] == "cn"


@pytest.mark.asyncio
async def test_region_us_via_org_handle(mock_http):
    """meta-llama author → region=us via 1st-signal org lookup."""
    mock_http(HF_TRENDING_URL, load_fixture("huggingface_trending.json"))
    items = await HuggingFaceApiCollector().collect()
    meta = next(it for it in items if "meta-llama" in it.title)
    assert meta.metadata["region"] == "us"


@pytest.mark.asyncio
async def test_region_global_fallback(mock_http):
    """Unknown org with no family substring → region=global."""
    mock_http(HF_TRENDING_URL, load_fixture("huggingface_trending.json"))
    items = await HuggingFaceApiCollector().collect()
    unknown = next(it for it in items if "randomuser" in it.title)
    assert unknown.metadata["region"] == "global"


@pytest.mark.asyncio
async def test_function_domain_tags_present(mock_http):
    """All items carry function=origin and domain=ecosystem in metadata."""
    mock_http(HF_TRENDING_URL, load_fixture("huggingface_trending.json"))
    items = await HuggingFaceApiCollector().collect()
    for it in items:
        assert it.metadata["function"] == "origin", f"{it.title}: missing function"
        assert it.metadata["domain"] == "ecosystem", f"{it.title}: missing domain"
