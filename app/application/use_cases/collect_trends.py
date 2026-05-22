from app.core.logger import get_logger
from app.domain.models.collected_item import CollectedItem
from app.domain.ports.collector import CollectorPort
from app.domain.ports.publisher import PublisherPort
from app.domain.ports.repository import ItemRepositoryPort
from app.domain.services.scoring_engine import apply_score
from app.domain.services.scoring_policies import BRIEFING_THRESHOLD

logger = get_logger(__name__)


class CollectTrendsUseCase:
    def __init__(
        self,
        collector: CollectorPort,
        repository: ItemRepositoryPort,
        publisher: PublisherPort | None = None,
    ) -> None:
        self._collector = collector
        self._repository = repository
        self._publisher = publisher

    async def execute(self) -> dict:
        items = await self._collector.collect()

        new_items: list[tuple[int, CollectedItem]] = []
        for item in items:
            if await self._repository.exists_by_hash(item.url_hash):
                continue
            apply_score(item)
            item_id = await self._repository.save(item)
            if item_id is None:
                continue
            new_items.append((item_id, item))
            logger.info(
                "Saved new item: %s [score=%d, importance=%s]",
                item.title,
                item.score,
                item.importance,
            )

        briefable = [
            (item_id, item)
            for item_id, item in new_items
            if item.score >= BRIEFING_THRESHOLD and not item.is_briefed
        ]

        briefed_count = 0
        if briefable and self._publisher is not None:
            try:
                await self._publisher.publish([item for _, item in briefable])
                for item_id, item in briefable:
                    await self._repository.mark_briefed(item_id)
                    item.is_briefed = True
                briefed_count = len(briefable)
            except Exception as exc:
                logger.exception("Briefing publish failed: %s", exc)

        logger.info(
            "Collect done — total=%d, new=%d, briefed=%d",
            len(items),
            len(new_items),
            briefed_count,
        )
        return {
            "total_collected": len(items),
            "new_items": len(new_items),
            "briefed": briefed_count,
        }
