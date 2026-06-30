from urllib.parse import urljoin

from bs4 import Tag

from app.core.datetime_utils import parse_date
from app.core.logger import get_logger
from app.domain.models.collected_item import CollectedItem
from app.domain.ports.collector import CollectorPort
from app.infrastructure.http.async_client import fetch_html

logger = get_logger(__name__)

BASE_URL = "https://mistral.ai"
NEWS_URL = f"{BASE_URL}/news/"

# Astro-generated static HTML (migrated from Next.js); articles carry data-title.
# Date appears as plain text in <footer> first <p>: "June 23, 2026"
_DATE_FORMATS = ("%B %d, %Y",)

KEYWORD_TAGS: dict[str, str] = {
    "mixtral": "mixtral",
    "moe": "moe",
    "mixture of experts": "moe",
    "reasoning": "reasoning",
    "multimodal": "multimodal",
    "open weight": "open-weight",
    "open-weight": "open-weight",
    "inference": "inference",
    "local": "local-ai",
    "enterprise": "enterprise-ai",
    "embedding": "embedding",
    "fine-tun": "fine-tuning",
    "agent": "agent",
    "vision": "vision",
    "audio": "audio",
    "speech": "speech",
    "code": "code",
}


def _keyword_tags(text: str) -> list[str]:
    lower = text.lower()
    return [tag for kw, tag in KEYWORD_TAGS.items() if kw in lower]


class MistralHtmlCollector(CollectorPort):
    async def collect(self) -> list[CollectedItem]:
        logger.info("Collecting from Mistral AI News: %s", NEWS_URL)
        soup = await fetch_html(NEWS_URL)

        articles = soup.find_all("article", attrs={"data-title": True})
        if not articles:
            logger.warning("No articles found — Mistral AI page structure may have changed")
            return []

        items: list[CollectedItem] = []
        seen_urls: set[str] = set()

        for art in articles:
            item = self._parse_article(art)
            if item is None or item.url in seen_urls:
                continue
            seen_urls.add(item.url)
            items.append(item)

        logger.info("Collected %d items from Mistral AI News", len(items))
        return items

    def _parse_article(self, art: Tag) -> CollectedItem | None:
        anchor = art.find("a")
        if not anchor:
            return None
        href: str = anchor.get("href", "")
        if not href:
            return None
        url = urljoin(BASE_URL, href)

        title_el = art.find(["h2", "h3", "h4"])
        title = title_el.get_text(strip=True) if title_el else art.get("data-title", "").title()
        if not title:
            return None

        footer = art.find("footer")
        date_text = ""
        if footer:
            first_p = footer.find("p")
            if first_p:
                date_text = first_p.get_text(strip=True)

        # Description: first <p> outside the footer that has meaningful text
        footer_ps = set(footer.find_all("p")) if footer else set()
        content_ps = [
            p for p in art.find_all("p")
            if p not in footer_ps and len(p.get_text(strip=True)) > 20
        ]
        desc = content_ps[0].get_text(strip=True) if content_ps else ""

        category = art.get("data-categories", "")
        published_at = parse_date(date_text, _DATE_FORMATS)
        tags = self._build_tags(title, desc, category)

        return CollectedItem(
            source="Mistral AI",
            title=title,
            url=url,
            published_at=published_at,
            summary=desc,
            tags=tags,
        )

    def _build_tags(self, title: str, summary: str, category: str) -> list[str]:
        tags = ["mistral"]
        combined = f"{title} {summary}".lower()
        for tag in _keyword_tags(combined):
            if tag not in tags:
                tags.append(tag)
        if category:
            cat_slug = category.lower().replace(" ", "-")
            if cat_slug not in tags:
                tags.append(cat_slug)
        return tags
