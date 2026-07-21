import asyncio

import feedparser

from app.core.datetime_utils import now_utc, parse_struct_time
from app.core.logger import get_logger
from app.domain.models.collected_item import CollectedItem
from app.domain.ports.collector import CollectorPort

logger = get_logger(__name__)

RSS_URL = "https://techcrunch.com/category/artificial-intelligence/feed/"
MAX_ITEMS = 50


class TechCrunchRssCollector(CollectorPort):
    async def collect(self) -> list[CollectedItem]:
        logger.info("Collecting from TechCrunch RSS: %s", RSS_URL)

        feed = await asyncio.to_thread(feedparser.parse, RSS_URL)

        if feed.bozo:
            logger.warning("Feed parse warning: %s", feed.bozo_exception)

        items: list[CollectedItem] = []
        for entry in feed.entries[:MAX_ITEMS]:
            published_at = (
                parse_struct_time(entry.published_parsed)
                if getattr(entry, "published_parsed", None)
                else now_utc()
            )

            raw_tags = entry.get("tags", [])
            categories = [t["term"].lower() for t in raw_tags]
            tags = ["techcrunch"] + categories

            items.append(
                CollectedItem(
                    source="TechCrunch",
                    title=entry.get("title", "").strip(),
                    url=entry.get("link", "").strip(),
                    published_at=published_at,
                    summary=entry.get("summary", "").strip(),
                    tags=tags,
                    metadata={
                        "function": "coverage",
                        "domain": "media",
                        "region": "us",
                        "feed": "techcrunch-ai",
                    },
                )
            )

        logger.info("Collected %d items from TechCrunch RSS", len(items))
        return items
