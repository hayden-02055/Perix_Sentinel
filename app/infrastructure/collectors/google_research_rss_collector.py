import asyncio
import re

import feedparser

from app.core.datetime_utils import now_utc, parse_struct_time
from app.core.logger import get_logger
from app.domain.models.collected_item import CollectedItem
from app.domain.ports.collector import CollectorPort

logger = get_logger(__name__)

RSS_URL = "https://research.google/blog/rss"

# A0: feed returns 100 entries; cap to match arXiv/NVIDIA convention.
MAX_ITEMS = 50

# A0: non-AI ratio 25% (>15% threshold) → filter applied.
# Category whitelist first; title keyword fallback if no category match.
_AI_CATEGORIES = frozenset({
    "machine intelligence",
    "generative ai",
    "natural language processing",
    "open source models & datasets",
    "responsible ai",
})

_AI_KEYWORD_RE = re.compile(
    r"\b(ai|ml|machine learning|deep learning|neural|language model|llm|nlp|"
    r"foundation model|transformer|embedding|fine.tun|gemini|bert|diffusion|"
    r"reinforcement|inference|training|model)\b",
    re.IGNORECASE,
)


def _is_ai_related(entry) -> bool:
    cats = {t["term"].lower() for t in entry.get("tags", [])}
    if cats & _AI_CATEGORIES:
        return True
    return bool(_AI_KEYWORD_RE.search(entry.get("title", "")))


class GoogleResearchRssCollector(CollectorPort):
    async def collect(self) -> list[CollectedItem]:
        logger.info("Collecting from Google Research RSS: %s", RSS_URL)

        feed = await asyncio.to_thread(feedparser.parse, RSS_URL)

        if feed.bozo:
            logger.warning("Feed parse warning: %s", feed.bozo_exception)

        items: list[CollectedItem] = []
        for entry in feed.entries[:MAX_ITEMS]:
            if not _is_ai_related(entry):
                continue

            published_at = (
                parse_struct_time(entry.published_parsed)
                if getattr(entry, "published_parsed", None)
                else now_utc()
            )

            raw_tags = entry.get("tags", [])
            categories = [t["term"].lower() for t in raw_tags]
            tags = ["google-research"] + categories

            items.append(
                CollectedItem(
                    source="Google Research",
                    title=entry.get("title", "").strip(),
                    url=entry.get("link", "").strip(),
                    published_at=published_at,
                    summary=entry.get("summary", "").strip(),
                    tags=tags,
                    metadata={
                        "function": "origin",
                        "domain": "core-lab",
                        "region": "us",
                        "feed": "research-blog",
                    },
                )
            )

        logger.info("Collected %d items from Google Research RSS", len(items))
        return items
