from app.core.logger import get_logger
from app.domain.ports.collector import CollectorPort
from app.domain.ports.repository import ItemRepositoryPort

logger = get_logger(__name__)


class CollectTrendsUseCase:
    def __init__(self, collector: CollectorPort, repository: ItemRepositoryPort) -> None:
        self._collector = collector
        self._repository = repository

    async def execute(self) -> dict:
        items = await self._collector.collect()

        new_count = 0
        for item in items:
            if not await self._repository.exists_by_hash(item.url_hash):
                await self._repository.save(item)
                new_count += 1
                logger.info("Saved new item: %s", item.title)

        logger.info("Collect done — total=%d, new=%d", len(items), new_count)
        return {"total_collected": len(items), "new_items": new_count}
