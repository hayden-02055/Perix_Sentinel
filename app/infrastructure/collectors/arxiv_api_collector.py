import asyncio
import re

import feedparser

from app.core.datetime_utils import now_utc, parse_struct_time
from app.core.logger import get_logger
from app.domain.models.collected_item import CollectedItem
from app.domain.ports.collector import CollectorPort

logger = get_logger(__name__)

_BASE_URL = "http://export.arxiv.org/api/query"
_CATEGORIES = ["cs.AI", "cs.CL", "cs.LG"]
_MAX_RESULTS = 50

QUERY_URL = (
    f"{_BASE_URL}"
    f"?search_query={'%20OR%20'.join(f'cat:{c}' for c in _CATEGORIES)}"
    f"&sortBy=submittedDate&sortOrder=descending"
    f"&start=0&max_results={_MAX_RESULTS}"
)


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


class ArxivApiCollector(CollectorPort):
    async def collect(self) -> list[CollectedItem]:
        logger.info("Collecting from arXiv API: %s", QUERY_URL)

        feed = await asyncio.to_thread(feedparser.parse, QUERY_URL)

        if feed.bozo:
            logger.warning("Feed parse warning: %s", feed.bozo_exception)

        items: list[CollectedItem] = []
        for entry in feed.entries:
            published_at = (
                parse_struct_time(entry.published_parsed)
                if getattr(entry, "published_parsed", None)
                else now_utc()
            )

            url = entry.get("link", entry.get("id", "")).replace("http://", "https://")
            title = _normalize(entry.get("title", ""))
            summary = _normalize(entry.get("summary", ""))

            raw_tags = entry.get("tags", [])
            categories = [t["term"].lower() for t in raw_tags]
            tags = ["arxiv"] + categories

            primary_cat = (entry.get("arxiv_primary_category") or {}).get("term", "")
            arxiv_id = ""
            raw_id = entry.get("id", "")
            if "/abs/" in raw_id:
                arxiv_id = raw_id.split("/abs/")[-1]

            authors = [a["name"] for a in entry.get("authors", [])]

            items.append(
                CollectedItem(
                    source="arXiv",
                    title=title,
                    url=url,
                    published_at=published_at,
                    summary=summary,
                    tags=tags,
                    metadata={
                        "authors": authors,
                        "primary_category": primary_cat,
                        "arxiv_id": arxiv_id,
                        "comment": entry.get("arxiv_comment", "") or "",
                    },
                )
            )

        logger.info("Collected %d items from arXiv", len(items))
        return items
