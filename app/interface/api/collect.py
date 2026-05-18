from fastapi import APIRouter

from app.application.use_cases.collect_trends import CollectTrendsUseCase
from app.infrastructure.collectors.anthropic_html_collector import AnthropicHtmlCollector
from app.infrastructure.collectors.openai_rss_collector import OpenAIRssCollector
from app.infrastructure.repositories.sqlite_item_repository import SqliteItemRepository

router = APIRouter()


@router.post("/collect")
async def trigger_collect() -> dict:
    repository = SqliteItemRepository()
    collectors = {
        "openai": OpenAIRssCollector(),
        "anthropic": AnthropicHtmlCollector(),
    }

    results: dict[str, dict] = {}
    for name, collector in collectors.items():
        use_case = CollectTrendsUseCase(collector=collector, repository=repository)
        results[name] = await use_case.execute()

    return results
