import asyncio
import html
import re

from app.core.datetime_utils import from_epoch, now_utc
from app.core.logger import get_logger
from app.domain.models.collected_item import CollectedItem
from app.domain.ports.collector import CollectorPort
from app.infrastructure.http.async_client import fetch_json

logger = get_logger(__name__)

_BASE_URL = "https://hacker-news.firebaseio.com/v0"
TOPSTORIES_URL = f"{_BASE_URL}/topstories.json"

N_TOP = 100
_CONCURRENCY = 10

AI_KEYWORDS = [
    "ai", "llm", "gpt", "claude", "gemini", "agent", "rag",
    "model", "neural", "ml", "diffusion", "transformer",
    "openai", "anthropic", "deepmind", "chatgpt", "copilot",
]

_AI_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(k) for k in AI_KEYWORDS) + r")\b",
    re.IGNORECASE,
)


def _item_url(item_id: int) -> str:
    return f"{_BASE_URL}/item/{item_id}.json"


def _discussion_url(item_id: int) -> str:
    return f"https://news.ycombinator.com/item?id={item_id}"


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def _matched_keywords(title: str) -> list[str]:
    seen: list[str] = []
    for m in _AI_PATTERN.findall(title):
        lower = m.lower()
        if lower not in seen:
            seen.append(lower)
    return seen


class HackerNewsApiCollector(CollectorPort):
    async def collect(self) -> list[CollectedItem]:
        logger.info("Collecting from Hacker News: %s", TOPSTORIES_URL)

        ids: list[int] = await fetch_json(TOPSTORIES_URL)
        ids = ids[:N_TOP]

        semaphore = asyncio.Semaphore(_CONCURRENCY)

        async def _fetch_item(item_id: int) -> dict | None:
            async with semaphore:
                try:
                    return await fetch_json(_item_url(item_id))
                except Exception as exc:
                    logger.warning("Failed to fetch HN item %d: %s", item_id, exc)
                    return None

        payloads = await asyncio.gather(*(_fetch_item(i) for i in ids))

        items: list[CollectedItem] = []
        for item_id, payload in zip(ids, payloads):
            if not payload or payload.get("type") != "story":
                continue

            title = _normalize(payload.get("title", ""))
            matched = _matched_keywords(title)
            if not matched:
                continue

            published_at = (
                from_epoch(payload["time"]) if payload.get("time") else now_utc()
            )
            url = payload.get("url") or _discussion_url(item_id)
            summary = _normalize(payload.get("text", "")) if payload.get("text") else ""

            items.append(
                CollectedItem(
                    source="Hacker News",
                    title=title,
                    url=url,
                    published_at=published_at,
                    summary=summary,
                    tags=["hackernews", payload.get("type", "")] + matched,
                    metadata={
                        "score": payload.get("score", 0),
                        "descendants": payload.get("descendants", 0),
                        "by": payload.get("by", ""),
                        "hn_id": item_id,
                        "type": payload.get("type", ""),
                    },
                )
            )

        logger.info("Collected %d AI-related items from Hacker News", len(items))
        return items
