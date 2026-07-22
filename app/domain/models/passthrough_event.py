"""PassthroughEvent — the source-agnostic exact-dedup Event (SDD §5).

Distinct from ``models.event.Event`` on purpose: that model is the origin/echo
shape backing the persisted ``events`` table (the reserved fuzzy slot).
``PassthroughEvent`` is computed **in-memory** on the read path (SDD §3
non-goal: no new persistence) and carries the amplification-signal fields
(``source_count``, ``source_diversity``, ...) that mostly equal 1 today.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from app.domain.models.collected_item import CollectedItem


@dataclass
class PassthroughEvent:
    event_id: str                       # md5(canonical_key) — deterministic
    canonical_url: str | None           # normalized primary URL (None if URL-less)
    title: str                          # primary_item.title
    items: list[CollectedItem]          # members (length 1 when passed through)
    primary_item: CollectedItem         # earliest published_at, source-name tiebreak (I1)
    source_count: int                   # len(distinct item.source)
    source_diversity: int               # len(distinct item.metadata["domain"]) (I4)
    sources: list[str] = field(default_factory=list)   # distinct source names
    domains: list[str] = field(default_factory=list)   # distinct metadata.domain
    regions: list[str] = field(default_factory=list)   # distinct metadata.region
    first_seen: datetime | None = None  # min(published_at)
    last_seen: datetime | None = None   # max(published_at)
