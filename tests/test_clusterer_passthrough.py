"""Golden + determinism tests for ExactDupClusterer (Passthrough Clusterer SDD §9).

Threshold-free and deterministic, so exact outputs can be asserted. The active
clusterer merges only on identical canonical_key (normalized URL, or normalized
title when URL-less) and passes everything else through as a 1-item event.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.domain.services.clusterer import ExactDupClusterer

BASE = datetime(2026, 7, 22, 12, 0, tzinfo=timezone.utc)


def _item(source, title, url, minutes=0, domain=None, region=None):
    from app.domain.models.collected_item import CollectedItem

    metadata = {}
    if domain is not None:
        metadata["domain"] = domain
    if region is not None:
        metadata["region"] = region
    return CollectedItem(
        source=source,
        title=title,
        url=url,
        published_at=BASE + timedelta(minutes=minutes),
        metadata=metadata,
    )


def _cluster(items):
    return ExactDupClusterer().cluster(items)


def test_g1_exact_duplicate_url_merges():
    """G1: identical URL from two sources → one Event, source_count=2."""
    items = [
        _item("Anthropic", "Claude Science", "https://anthropic.com/claude-science", 0, "core-lab"),
        _item("Hacker News", "Claude Science (discussion)", "https://anthropic.com/claude-science", 30, "community"),
    ]
    events = _cluster(items)
    assert len(events) == 1
    assert events[0].source_count == 2
    assert sorted(events[0].sources) == ["Anthropic", "Hacker News"]
    # primary = earliest published_at (I1)
    assert events[0].primary_item.source == "Anthropic"
    # source_diversity = distinct domain (I4)
    assert events[0].source_diversity == 2


def test_g2_url_normalization_merges_utm_variants():
    """G2: same URL differing only by ?utm_source=x → one Event."""
    items = [
        _item("OpenAI", "GPT-6 released", "https://openai.com/blog/gpt-6", 0),
        _item("TechCrunch", "OpenAI ships GPT-6", "https://openai.com/blog/gpt-6?utm_source=tc&ref=feed", 60),
    ]
    events = _cluster(items)
    assert len(events) == 1
    assert events[0].source_count == 2
    assert events[0].canonical_url == "https://openai.com/blog/gpt-6"


def test_g3_distinct_urls_pass_through():
    """G3: N distinct URLs → N Events, all source_count=1."""
    items = [
        _item("OpenAI", "A", "https://openai.com/a", 0),
        _item("Meta", "B", "https://meta.com/b", 10),
        _item("NVIDIA", "C", "https://nvidia.com/c", 20),
    ]
    events = _cluster(items)
    assert len(events) == 3
    assert all(e.source_count == 1 for e in events)


def test_g4_true_positive_not_merged_by_design():
    """G4: Anthropic vs HN 'Claude Science' with different URLs → 2 Events.

    This is the sole real origin↔origin positive; passthrough must NOT merge it
    (no fuzzy matching). Different URL → different canonical_key → separate.
    """
    items = [
        _item("Anthropic", "Claude Science", "https://anthropic.com/claude-science", 0),
        _item("Hacker News", "Claude Science", "https://news.ycombinator.com/item?id=999", 60),
    ]
    events = _cluster(items)
    assert len(events) == 2
    assert all(e.source_count == 1 for e in events)


def test_g5_url_less_items_use_title_fallback():
    """G5: URL-less items key on normalized title; same title merges, different splits."""
    same = [
        _item("SourceA", "Model Zeta launches", "", 0),
        _item("SourceB", "model   zeta   launches", "", 30),  # case/whitespace differ only
    ]
    events = _cluster(same)
    assert len(events) == 1
    assert events[0].source_count == 2
    assert events[0].canonical_url is None

    different = [
        _item("SourceA", "Alpha news", "", 0),
        _item("SourceB", "Beta news", "", 30),
    ]
    assert len(_cluster(different)) == 2


def test_determinism_same_input_same_output():
    """Same input twice → identical event order and ids."""
    items = [
        _item("OpenAI", "A", "https://openai.com/a", 0),
        _item("TechCrunch", "A echo", "https://openai.com/a?utm_source=x", 30),
        _item("Meta", "B", "https://meta.com/b", 10),
    ]
    first = _cluster(items)
    second = _cluster(list(reversed(items)))  # input order must not matter
    assert [e.event_id for e in first] == [e.event_id for e in second]
    assert [e.title for e in first] == [e.title for e in second]


def test_source_agnostic_no_hardcoded_branching():
    """A coverage source (TechCrunch) and origin merge purely on canonical_key,
    with no origin/echo role distinction — proving source-agnostic behavior."""
    items = [
        _item("TechCrunch", "X", "https://x.com/y", 0),
        _item("Anthropic", "X", "https://x.com/y", 30),
    ]
    events = _cluster(items)
    assert len(events) == 1
    assert events[0].source_count == 2
