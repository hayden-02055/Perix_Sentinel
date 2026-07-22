"""GenerateEventsUseCase — read stored items → cluster → in-memory events.

Passthrough Clusterer SDD §A3. This is the least-invasive wiring point: it
reads persisted items and clusters them on a *read* path, leaving the live
per-item collect/brief path (``CollectTrendsUseCase``) untouched. Per SDD §3
non-goal, events are computed in memory and NOT persisted to the events table.
"""
from __future__ import annotations

from app.core.logger import get_logger
from app.domain.models.passthrough_event import PassthroughEvent
from app.domain.ports.clusterer_port import ClustererPort
from app.domain.ports.repository import ItemRepositoryPort
from app.domain.services.briefing_generator import generate_briefing

logger = get_logger(__name__)


class GenerateEventsUseCase:
    def __init__(self, repository: ItemRepositoryPort, clusterer: ClustererPort) -> None:
        self._repository = repository
        self._clusterer = clusterer

    async def execute(self, limit: int = 500) -> list[PassthroughEvent]:
        items = await self._repository.get_recent(limit=limit)
        events = self._clusterer.cluster(items)
        merged = sum(1 for e in events if e.source_count > 1)
        logger.info(
            "Generated events — items=%d, events=%d, merged=%d",
            len(items),
            len(events),
            merged,
        )
        # collect → cluster → brief: exercise the briefing path in-memory on the
        # primary item so the wiring is proven end-to-end without publishing.
        for event in events:
            generate_briefing(event.primary_item)
        return events
