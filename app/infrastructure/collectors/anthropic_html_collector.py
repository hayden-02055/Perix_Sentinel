from app.core.datetime_utils import parse_date
from app.core.logger import get_logger
from app.domain.models.collected_item import CollectedItem
from app.domain.ports.collector import CollectorPort
from app.infrastructure.http.async_client import fetch_html

logger = get_logger(__name__)

BASE_URL = "https://www.anthropic.com"
NEWS_URL = f"{BASE_URL}/news"

_DATE_FORMATS = ("%b %d, %Y",)


class AnthropicHtmlCollector(CollectorPort):
    async def collect(self) -> list[CollectedItem]:
        logger.info("Collecting from Anthropic News page: %s", NEWS_URL)
        soup = await fetch_html(NEWS_URL)

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
            raw_date = time_el.get_text(strip=True) if time_el else ""
            published_at = parse_date(raw_date, _DATE_FORMATS)

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
