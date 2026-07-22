"""Clusterer — two implementations, one active (SDD Passthrough Clusterer §6).

ACTIVE: ``ExactDupClusterer`` (SDD Passthrough Clusterer, this phase).
Source-agnostic, deterministic, threshold-free. Merges items only when their
``canonical_key`` (normalized URL, or normalized title when URL-less) is
identical; everything else passes through as a 1-item ``PassthroughEvent``.

ISOLATED (fuzzy slot, NOT deleted): ``FuzzyClusterer`` wraps the legacy
3-gate matching from the earlier A2a SDD (time window → entity intersect →
Jaccard tiebreak, with source-name special-casing). It is retained verbatim
as the polishing-phase replacement point and is intentionally NOT wired into
the active pipeline. The empirical case for enabling it is absent (origin↔origin
0.06%, origin↔coverage 0% — see docs/notes/clusterer-*-a0*.md).
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone

from app.core.config import MATCH_WINDOW_AFTER_H, MATCH_WINDOW_BEFORE_H
from app.core.url_utils import canonical_key, normalize_url
from app.domain.models.collected_item import CollectedItem
from app.domain.models.event import Event, EventMember
from app.domain.models.passthrough_event import PassthroughEvent
from app.domain.ports.clusterer_port import ClustererPort
from app.domain.services.entity_extractor import extract_entities, tokenize


# ---------------------------------------------------------------------------
# ACTIVE — ExactDupClusterer (SDD Passthrough Clusterer §5)
# ---------------------------------------------------------------------------

def _has_url(item: CollectedItem) -> bool:
    return bool(item.url and item.url.strip())


def _distinct_sorted(values) -> list[str]:
    return sorted({v for v in values if v})


def _aware(dt: datetime) -> datetime:
    """Coerce a legacy naive datetime (some pre-refactor DB rows) to UTC-aware
    so ordering never mixes naive and aware. New items are already aware."""
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def _build_event(key: str, members: list[CollectedItem]) -> PassthroughEvent:
    # Stable primary selection (I1): earliest published_at, tiebreak on source name.
    ordered = sorted(members, key=lambda i: (_aware(i.published_at), i.source))
    primary = ordered[0]

    domains = _distinct_sorted(i.metadata.get("domain") for i in ordered)
    regions = _distinct_sorted(i.metadata.get("region") for i in ordered)
    published = [_aware(i.published_at) for i in ordered]

    return PassthroughEvent(
        event_id=hashlib.md5(key.encode()).hexdigest(),
        canonical_url=normalize_url(primary.url) if _has_url(primary) else None,
        title=primary.title,
        items=ordered,
        primary_item=primary,
        source_count=len({i.source for i in ordered}),
        source_diversity=len(domains),
        sources=_distinct_sorted(i.source for i in ordered),
        domains=domains,
        regions=regions,
        first_seen=min(published),
        last_seen=max(published),
    )


class ExactDupClusterer(ClustererPort):
    """Merge items with an identical ``canonical_key``; pass the rest through.

    Deterministic and source-agnostic — no ``if source == ...`` branching, no
    thresholds. Output order is stable regardless of input order: events are
    sorted by ``(first_seen, event_id)``.
    """

    def cluster(self, items: list[CollectedItem]) -> list[PassthroughEvent]:
        groups: dict[str, list[CollectedItem]] = {}
        for item in items:
            key = canonical_key(item.url, item.title)
            groups.setdefault(key, []).append(item)

        events = [_build_event(key, members) for key, members in groups.items()]
        events.sort(key=lambda e: (e.first_seen, e.event_id))
        return events


# ---------------------------------------------------------------------------
# ISOLATED — legacy fuzzy 3-gate matching (polishing slot, not wired)
# ---------------------------------------------------------------------------

_COVERAGE_SOURCES = {"TechCrunch", "MarkTechPost"}
_HUGGINGFACE_SOURCE = "HuggingFace"


def _to_member(item: CollectedItem, role: str) -> EventMember:
    return EventMember(
        item_hash=item.url_hash,
        role=role,
        source=item.source,
        title=item.title,
        url=item.url,
        published_at=item.published_at,
    )


def _serialize_entities(entities: dict) -> dict:
    return {
        "org": sorted(entities["org"]),
        "model": sorted(family + version for family, version in entities["model"]),
    }


def _new_event(origin: CollectedItem, entities: dict) -> Event:
    event_id = hashlib.md5(origin.url_hash.encode()).hexdigest()
    return Event(
        title=origin.title,
        occurred_at=origin.published_at,
        members=[_to_member(origin, role="origin")],
        entities=_serialize_entities(entities),
        event_id=event_id,
    )


def _gate1_time_window(origin: CollectedItem, coverage: CollectedItem) -> bool:
    lower = origin.published_at - timedelta(hours=MATCH_WINDOW_BEFORE_H)
    upper = origin.published_at + timedelta(hours=MATCH_WINDOW_AFTER_H)
    return lower <= coverage.published_at <= upper


def _models_intersect(a: set[tuple[str, str]], b: set[tuple[str, str]]) -> bool:
    for family_a, version_a in a:
        for family_b, version_b in b:
            if family_a != family_b:
                continue
            if not version_a or not version_b or version_a == version_b:
                return True
    return False


def _gate2_entity(origin_entities: dict, coverage_entities: dict, candidate_count: int) -> bool:
    if not (origin_entities["org"] & coverage_entities["org"]):
        return False
    if candidate_count == 1:
        return True
    return _models_intersect(origin_entities["model"], coverage_entities["model"])


def _jaccard(a_tokens: set[str], b_tokens: set[str]) -> float:
    union = a_tokens | b_tokens
    if not union:
        return 0.0
    return len(a_tokens & b_tokens) / len(union)


def _gate3_tiebreak(
    candidate_idxs: list[int],
    origin_items: list[CollectedItem],
    coverage: CollectedItem,
) -> int:
    non_hf = [idx for idx in candidate_idxs if origin_items[idx].source != _HUGGINGFACE_SOURCE]
    if non_hf:
        pool, use_jaccard = non_hf, True
    else:
        pool, use_jaccard = candidate_idxs, False

    if len(pool) == 1:
        return pool[0]

    tied = pool
    if use_jaccard:
        coverage_tokens = set(tokenize(coverage.title))
        scores = {idx: _jaccard(set(tokenize(origin_items[idx].title)), coverage_tokens) for idx in pool}
        best_score = max(scores.values())
        tied = [idx for idx in pool if scores[idx] == best_score]
        if len(tied) == 1:
            return tied[0]

    return min(
        tied,
        key=lambda idx: abs((origin_items[idx].published_at - coverage.published_at).total_seconds()),
    )


def _legacy_fuzzy_cluster(items: list[CollectedItem]) -> list[Event]:
    origin_items = [i for i in items if i.source not in _COVERAGE_SOURCES]
    coverage_items = [i for i in items if i.source in _COVERAGE_SOURCES]

    origin_entities = [extract_entities(o.title) for o in origin_items]
    events = [_new_event(o, e) for o, e in zip(origin_items, origin_entities)]

    for coverage in coverage_items:
        coverage_entities = extract_entities(coverage.title)

        candidate_idxs = [
            idx for idx, o in enumerate(origin_items) if _gate1_time_window(o, coverage)
        ]
        # "Unique candidate" (§6) means unique within the same org, not unique across
        # the whole time window — an unrelated org sharing the window must not force
        # a same-org candidate to need a model match it has no reason to have.
        org_overlap_count = sum(
            1
            for idx in candidate_idxs
            if origin_entities[idx]["org"] & coverage_entities["org"]
        )
        candidate_idxs = [
            idx
            for idx in candidate_idxs
            if _gate2_entity(origin_entities[idx], coverage_entities, org_overlap_count)
        ]

        if not candidate_idxs:
            continue

        chosen_idx = (
            candidate_idxs[0]
            if len(candidate_idxs) == 1
            else _gate3_tiebreak(candidate_idxs, origin_items, coverage)
        )
        events[chosen_idx].members.append(_to_member(coverage, role="echo"))

    for event in events:
        echoes = [m for m in event.members if m.role == "echo"]
        event.echo_count = len(echoes)
        event.diversity = len({m.source for m in echoes})

    return events


class FuzzyClusterer:
    """Isolated legacy fuzzy 3-gate clusterer (polishing slot, not wired).

    Returns the legacy origin/echo ``Event`` shape — deliberately does not
    implement ``ClustererPort`` (different return type). Kept only so the
    threshold-based logic and its tests survive for a future re-measurement.
    """

    def cluster(self, items: list[CollectedItem]) -> list[Event]:
        return _legacy_fuzzy_cluster(items)
