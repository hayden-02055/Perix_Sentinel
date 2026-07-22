"""Read-only clustering endpoint (Passthrough Clusterer SDD §A3).

Reads stored items, runs the exact-dedup passthrough clusterer, and returns a
summary. No persistence, no Discord publish — the live collect path is
untouched.
"""
from fastapi import APIRouter

from app.application.use_cases.generate_events import GenerateEventsUseCase
from app.domain.services.clusterer import ExactDupClusterer
from app.infrastructure.repositories.sqlite_item_repository import SqliteItemRepository

router = APIRouter()


@router.post("/cluster/preview")
async def cluster_preview(limit: int = 500) -> dict:
    use_case = GenerateEventsUseCase(
        repository=SqliteItemRepository(),
        clusterer=ExactDupClusterer(),
    )
    events = await use_case.execute(limit=limit)
    merged = [e for e in events if e.source_count > 1]
    return {
        "items_scanned": sum(len(e.items) for e in events),
        "event_count": len(events),
        "merged_event_count": len(merged),
        "merged_examples": [
            {
                "event_id": e.event_id,
                "title": e.title,
                "canonical_url": e.canonical_url,
                "source_count": e.source_count,
                "sources": e.sources,
            }
            for e in merged[:10]
        ],
    }
