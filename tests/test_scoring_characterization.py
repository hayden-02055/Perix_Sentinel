"""Characterization tests for the scoring engine.

These pin the *current* input -> output of ``calculate_score`` / ``apply_score``
so any refactor that claims to be behavior-preserving must keep these scores,
reasons and importance labels identical. ``now`` is always injected to keep
recency deterministic.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.domain.models.collected_item import CollectedItem
from app.domain.services.scoring_engine import apply_score, calculate_score
from app.domain.services.scoring_policies import classify_importance

NOW = datetime(2026, 7, 1, 12, 0, 0)


def _item(**kw) -> CollectedItem:
    base = dict(title="", url="u", published_at=NOW, summary="", tags=[])
    base.update(kw)
    return CollectedItem(**base)


# (name, item, expected breakdown dict, expected reason, expected importance)
CASES = [
    (
        "openai_agent_recent",
        _item(
            source="OpenAI",
            title="New Agent with MCP",
            published_at=datetime(2026, 7, 1, 0, 0),
            summary="reasoning gpt",
            tags=["agent"],
        ),
        dict(source=10, keyword=19, popularity=0, recency=5, total=34,
             matched=["agent", "mcp", "reasoning", "gpt"]),
        "keywords=agent,mcp,reasoning,gpt | recency=5 | source=10",
        "critical",
    ),
    (
        "hf_popular",
        _item(
            source="HuggingFace",
            title="llama model",
            published_at=datetime(2026, 6, 29, 0, 0),
            tags=["llama"],
            metadata={"likes": 350, "downloads": 50000},
        ),
        dict(source=7, keyword=4, popularity=8, recency=3, total=22,
             matched=["llama"]),
        "keywords=llama | popularity=8 | recency=3 | source=7",
        "high",
    ),
    (
        "github_popular",
        _item(
            source="GitHub Trending",
            title="owner/repo",
            published_at=datetime(2026, 7, 1, 0, 0),
            summary="rag agent",
            tags=["github"],
            metadata={"stars": 12000, "stars_today": 250},
        ),
        dict(source=7, keyword=9, popularity=3, recency=5, total=24,
             matched=["agent", "rag"]),
        "keywords=agent,rag | popularity=3 | recency=5 | source=7",
        "high",
    ),
    (
        "old_lowsource",
        _item(
            source="Mistral AI",
            title="Mixtral MoE release",
            published_at=datetime(2026, 6, 1, 0, 0),
            summary="open-weight inference",
        ),
        dict(source=8, keyword=14, popularity=0, recency=0, total=22,
             matched=["mixtral", "moe", "inference", "open-weight"]),
        "keywords=mixtral,moe,inference,open-weight | source=8",
        "high",
    ),
    (
        "unknown_source",
        _item(source="RandomBlog", title="nothing special",
              published_at=datetime(2026, 6, 20, 0, 0)),
        dict(source=0, keyword=0, popularity=0, recency=0, total=0, matched=[]),
        "source=0",
        "low",
    ),
]


@pytest.mark.parametrize("name, item, expected, reason, importance", CASES,
                         ids=[c[0] for c in CASES])
def test_calculate_score_breakdown(name, item, expected, reason, importance):
    b = calculate_score(item, now=NOW)
    assert b.source_score == expected["source"]
    assert b.keyword_score == expected["keyword"]
    assert b.popularity_score == expected["popularity"]
    assert b.recency_score == expected["recency"]
    assert b.total == expected["total"]
    assert b.matched_keywords == expected["matched"]
    assert b.reason() == reason
    assert classify_importance(b.total) == importance


def test_apply_score_mutates_item():
    item = CASES[0][1]
    breakdown = apply_score(item, now=NOW)
    assert item.score == breakdown.total == 34
    assert item.importance == "critical"
    assert item.reason == "keywords=agent,mcp,reasoning,gpt | recency=5 | source=10"


@pytest.mark.parametrize(
    "score, label",
    [(9, "low"), (10, "normal"), (14, "normal"), (15, "high"),
     (24, "high"), (25, "critical"), (30, "critical")],
)
def test_classify_importance_thresholds(score, label):
    assert classify_importance(score) == label


# ── Regression: aware UTC now + aware UTC published_at must not raise ────────

NOW_UTC = datetime(2026, 7, 1, 12, 0, 0, tzinfo=timezone.utc)


def test_recency_score_aware_now_and_aware_published():
    """Production path: both now and published_at are timezone-aware UTC."""
    item = CollectedItem(
        source="OpenAI",
        title="t",
        url="u",
        published_at=datetime(2026, 7, 1, 0, 0, tzinfo=timezone.utc),
        summary="",
        tags=[],
    )
    b = calculate_score(item, now=NOW_UTC)
    assert b.recency_score == 5


def test_recency_score_naive_now_and_naive_published():
    """Legacy path (test fixtures): both naive — same score as before P1."""
    item = CollectedItem(
        source="OpenAI",
        title="t",
        url="u",
        published_at=datetime(2026, 7, 1, 0, 0),
        summary="",
        tags=[],
    )
    b = calculate_score(item, now=NOW)
    assert b.recency_score == 5


def test_recency_score_aware_now_and_naive_published():
    """Mixed path: now aware, published naive — should not raise."""
    item = CollectedItem(
        source="OpenAI",
        title="t",
        url="u",
        published_at=datetime(2026, 7, 1, 0, 0),
        summary="",
        tags=[],
    )
    b = calculate_score(item, now=NOW_UTC)
    assert b.recency_score == 5
