from dataclasses import dataclass
from datetime import datetime

from app.domain.models.collected_item import CollectedItem
from app.domain.services.scoring_policies import (
    KEYWORD_WEIGHTS,
    SOURCE_WEIGHTS,
    classify_importance,
)


@dataclass
class ScoreBreakdown:
    source_score: int
    keyword_score: int
    popularity_score: int
    recency_score: int
    matched_keywords: list[str]

    @property
    def total(self) -> int:
        return (
            self.source_score
            + self.keyword_score
            + self.popularity_score
            + self.recency_score
        )

    def reason(self) -> str:
        parts: list[str] = []
        if self.matched_keywords:
            parts.append("keywords=" + ",".join(self.matched_keywords))
        if self.popularity_score:
            parts.append(f"popularity={self.popularity_score}")
        if self.recency_score:
            parts.append(f"recency={self.recency_score}")
        parts.append(f"source={self.source_score}")
        return " | ".join(parts)


def _source_score(item: CollectedItem) -> int:
    return SOURCE_WEIGHTS.get(item.source, 0)


def _keyword_score(item: CollectedItem) -> tuple[int, list[str]]:
    haystack = " ".join([item.title, item.summary, " ".join(item.tags)]).lower()
    matched: list[str] = []
    total = 0
    for keyword, weight in KEYWORD_WEIGHTS.items():
        if keyword in haystack:
            total += weight
            matched.append(keyword)
    return total, matched


def _popularity_score(item: CollectedItem) -> int:
    meta = item.metadata or {}
    if item.source == "HuggingFace":
        likes = float(meta.get("likes", 0) or 0)
        downloads = float(meta.get("downloads", 0) or 0)
        return int(min(likes / 100, 5) + min(downloads / 10000, 5))
    if item.source == "GitHub Trending":
        stars = float(meta.get("stars", 0) or 0)
        stars_today = float(meta.get("stars_today", 0) or 0)
        return int(min(stars_today / 100, 10) + min(stars / 10000, 5))
    return 0


def _recency_score(item: CollectedItem, now: datetime) -> int:
    published = item.published_at
    if published.tzinfo is not None:
        published = published.replace(tzinfo=None)
    age_days = (now - published).total_seconds() / 86400
    if age_days <= 1:
        return 5
    if age_days <= 3:
        return 3
    if age_days <= 7:
        return 1
    return 0


def calculate_score(item: CollectedItem, *, now: datetime | None = None) -> ScoreBreakdown:
    now = now or datetime.utcnow()
    keyword_total, matched = _keyword_score(item)
    return ScoreBreakdown(
        source_score=_source_score(item),
        keyword_score=keyword_total,
        popularity_score=_popularity_score(item),
        recency_score=_recency_score(item, now),
        matched_keywords=matched,
    )


def apply_score(item: CollectedItem, *, now: datetime | None = None) -> ScoreBreakdown:
    breakdown = calculate_score(item, now=now)
    item.score = breakdown.total
    item.importance = classify_importance(item.score)
    item.reason = breakdown.reason()
    return breakdown
