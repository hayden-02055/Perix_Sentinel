from datetime import datetime

import httpx
from bs4 import BeautifulSoup

from app.core.logger import get_logger
from app.domain.models.collected_item import CollectedItem
from app.domain.ports.collector import CollectorPort

logger = get_logger(__name__)

BASE_URL = "https://www.anthropic.com"
NEWS_URL = f"{BASE_URL}/news"


class AnthropicHtmlCollector(CollectorPort):
    async def collect(self) -> list[CollectedItem]:
        logger.info("Collecting from Anthropic News page: %s", NEWS_URL)

        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=15.0,
            headers={"User-Agent": "Mozilla/5.0"},
        ) as client:
            response = await client.get(NEWS_URL)
            response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        items: list[CollectedItem] = []
        seen_urls: set[str] = set()

        for anchor in soup.select('a[href^="/news/"]'):
            href = anchor.get("href", "")
            if not href or href == "/news":
                continue
            url = BASE_URL + href
            if url in seen_urls:
                continue
            seen_urls.add(url)

            title_el = anchor.find(["h1", "h2", "h3", "h4", "h5"]) or anchor.select_one(
                '[class*="title"]'
            )
            time_el = anchor.find("time")
            body_el = anchor.find("p")

            title = title_el.get_text(strip=True) if title_el else ""
            if not title:
                continue

            summary = body_el.get_text(strip=True) if body_el else ""
            published_at = self._parse_date(
                time_el.get_text(strip=True) if time_el else ""
            )

            items.append(
                CollectedItem(
                    source="Anthropic",
                    title=title,
                    url=url,
                    published_at=published_at,
                    summary=summary,
                    tags=["anthropic"],
                )
            )

        logger.info("Collected %d items from Anthropic News", len(items))
        return items

    def _parse_date(self, text: str) -> datetime:
        if text:
            try:
                return datetime.strptime(text, "%b %d, %Y")
            except ValueError:
                logger.warning("Failed to parse Anthropic date: %s", text)
        return datetime.utcnow()
