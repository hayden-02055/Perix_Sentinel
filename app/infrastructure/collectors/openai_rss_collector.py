import asyncio

import feedparser

from app.core.datetime_utils import now_utc, parse_struct_time
from app.core.logger import get_logger
from app.domain.models.collected_item import CollectedItem
from app.domain.ports.collector import CollectorPort

logger = get_logger(__name__)

RSS_URL = "https://openai.com/news/rss.xml"


class OpenAIRssCollector(CollectorPort):
    async def collect(self) -> list[CollectedItem]:
        logger.info("Collecting from OpenAI RSS: %s", RSS_URL)

        feed = await asyncio.to_thread(feedparser.parse, RSS_URL)

        if feed.bozo:
            logger.warning("Feed parse warning: %s", feed.bozo_exception)

        items: list[CollectedItem] = []
        for entry in feed.entries:
            published_at = (
                parse_struct_time(entry.published_parsed)
                if getattr(entry, "published_parsed", None)
                else now_utc()
            )
            items.append(
                CollectedItem(
                    source="OpenAI",
                    title=entry.get("title", "").strip(),
                    url=entry.get("link", "").strip(),
                    published_at=published_at,
                    summary=entry.get("summary", "").strip(),
                    tags=["openai"],
                )
            )

        logger.info("Collected %d items from OpenAI RSS", len(items))
        return items


