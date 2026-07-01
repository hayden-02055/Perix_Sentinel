from fastapi import APIRouter

from app.application.use_cases.collect_trends import CollectTrendsUseCase
from app.infrastructure.collectors.anthropic_html_collector import AnthropicHtmlCollector
from app.infrastructure.collectors.arxiv_api_collector import ArxivApiCollector
from app.infrastructure.collectors.deepmind_html_collector import DeepmindHtmlCollector
from app.infrastructure.collectors.github_trending_collector import GitHubTrendingCollector
from app.infrastructure.collectors.hackernews_api_collector import HackerNewsApiCollector
from app.infrastructure.collectors.huggingface_api_collector import HuggingFaceApiCollector
from app.infrastructure.collectors.meta_html_collector import MetaHtmlCollector
from app.infrastructure.collectors.mistral_html_collector import MistralHtmlCollector
from app.infrastructure.collectors.nvidia_rss_collector import NvidiaRssCollector
from app.infrastructure.collectors.openai_rss_collector import OpenAIRssCollector
from app.infrastructure.publishers.discord_publisher import DiscordPublisher
from app.infrastructure.repositories.sqlite_item_repository import SqliteItemRepository

router = APIRouter()


@router.post("/collect")
async def trigger_collect() -> dict:
    repository = SqliteItemRepository()
    publisher = DiscordPublisher()
    collectors = {
        "openai": OpenAIRssCollector(),
        "arxiv": ArxivApiCollector(),
        "anthropic": AnthropicHtmlCollector(),
        "deepmind": DeepmindHtmlCollector(),
        "meta": MetaHtmlCollector(),
        "mistral": MistralHtmlCollector(),
        "huggingface": HuggingFaceApiCollector(),
        "github": GitHubTrendingCollector(),
        "hackernews": HackerNewsApiCollector(),
        "nvidia": NvidiaRssCollector(),
    }

    results: dict[str, dict] = {}
    for name, collector in collectors.items():
        use_case = CollectTrendsUseCase(
            collector=collector,
            repository=repository,
            publisher=publisher,
        )
        results[name] = await use_case.execute()

    return results
