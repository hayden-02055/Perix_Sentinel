"""Clusterer (SDD Perix_Sentinel_Clusterer_Impl_SDD_A2a_A3 §6).

Pure function, no I/O / DB access — `cluster(items) -> list[Event]`. Every
origin item becomes exactly one Event (possibly with zero echo members);
coverage items attach as echo members to at most one Event, or attach to
none ("미귀속, 폐기 아님" — simply absent from the return value, the item
itself is left untouched for a future run).

Gate order matters (§6 pseudocode / test_clusterer_time_window): time
window is evaluated before the entity gate, so a same-family model within
the org can still be rejected purely on elapsed time (see the "NVIDIA
Cosmos 3" A0 case, +159h).
"""
from __future__ import annotations

import hashlib
from datetime import timedelta

from app.core.config import MATCH_WINDOW_AFTER_H, MATCH_WINDOW_BEFORE_H
from app.domain.models.collected_item import CollectedItem
from app.domain.models.event import Event, EventMember
from app.domain.services.entity_extractor import extract_entities, tokenize

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


def cluster(items: list[CollectedItem]) -> list[Event]:
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
