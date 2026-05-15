from fastapi import APIRouter

from app.application.use_cases.collect_trends import CollectTrendsUseCase
from app.infrastructure.collectors.openai_rss_collector import OpenAIRssCollector
from app.infrastructure.repositories.sqlite_item_repository import SqliteItemRepository

router = APIRouter()


@router.post("/collect")
async def trigger_collect() -> dict:
    use_case = CollectTrendsUseCase(
        collector=OpenAIRssCollector(),
        repository=SqliteItemRepository(),
    )
    return await use_case.execute()
