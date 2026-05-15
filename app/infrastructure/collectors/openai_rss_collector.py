import asyncio
from datetime import datetime

import feedparser

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
            published_at = self._parse_date(entry)
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

    def _parse_date(self, entry) -> datetime:
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            return datetime(*entry.published_parsed[:6])
        return datetime.utcnow()
