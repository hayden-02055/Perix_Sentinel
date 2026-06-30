from urllib.parse import urljoin, urlparse

from bs4 import Tag

from app.core.datetime_utils import now_utc, try_parse_date
from app.core.logger import get_logger
from app.domain.models.collected_item import CollectedItem
from app.domain.ports.collector import CollectorPort
from app.infrastructure.http.async_client import fetch_html

logger = get_logger(__name__)

BASE_URL = "https://deepmind.google"
BLOG_URL = f"{BASE_URL}/blog/"

ALLOWED_DOMAINS = {"deepmind.google", "blog.google"}

_DATE_FORMATS = ("%B %Y", "%B %d, %Y", "%b %d, %Y", "%Y-%m-%d")


def _resolve_url(href: str) -> str:
    if href.startswith("http"):
        return href
    return urljoin(BASE_URL, href)


def _is_allowed_url(url: str) -> bool:
    return urlparse(url).netloc in ALLOWED_DOMAINS


class DeepmindHtmlCollector(CollectorPort):
    async def collect(self) -> list[CollectedItem]:
        logger.info("Collecting from DeepMind Blog: %s", BLOG_URL)
        soup = await fetch_html(BLOG_URL)

        # card__overlay-link 기준으로 카드 컨테이너(부모) 탐색
        card_links = soup.select("a.card__overlay-link[href]")
        if not card_links:
            logger.warning("No card links found — DeepMind HTML structure may have changed")

        items: list[CollectedItem] = []
        seen_urls: set[str] = set()

        for anchor in card_links:
            href: str = anchor["href"]
            url = _resolve_url(href)

            if not _is_allowed_url(url):
                continue
            if url in seen_urls:
                continue
            seen_urls.add(url)

            # title/date/category 는 sibling 인 card__content 안에 있음
            card = anchor.parent
            if not isinstance(card, Tag):
                continue

            title = self._extract_title(anchor, card)
            if not title:
                continue

            published_at = self._extract_date(card)
            tags = self._extract_tags(card)

            items.append(
                CollectedItem(
                    source="DeepMind",
                    title=title,
                    url=url,
                    published_at=published_at,
                    summary="",
                    tags=tags,
                )
            )

        logger.info("Collected %d items from DeepMind Blog", len(items))
        return items

    def _extract_title(self, anchor: Tag, card: Tag) -> str:
        # 카드 컨텐츠의 heading 우선
        heading = card.find(["h1", "h2", "h3", "h4", "h5"])
        if heading:
            return heading.get_text(strip=True)

        # data-event-content-name 속성 폴백 (예: "Article Title - Learn more")
        event_name: str = anchor.get("data-event-content-name", "")
        if event_name:
            return event_name.removesuffix(" - Learn more").strip()

        logger.debug("Title not found for: %s", anchor.get("href"))
        return ""

    def _extract_date(self, card: Tag):
        time_el = card.find("time")
        if not time_el:
            return now_utc()

        datetime_attr: str = time_el.get("datetime", "")
        text: str = time_el.get_text(strip=True)

        for raw in [datetime_attr, text]:
            if not raw:
                continue
            dt = try_parse_date(raw, _DATE_FORMATS)
            if dt is not None:
                return dt

        logger.warning("Failed to parse DeepMind date: attr=%r text=%r", datetime_attr, text)
        return now_utc()

    def _extract_tags(self, card: Tag) -> list[str]:
        tags = ["deepmind", "google"]

        category_el = card.select_one(".meta__category") or card.select_one('[class*="category"]')
        if category_el:
            category = category_el.get_text(strip=True).lower()
            if category and category not in tags:
                tags.append(category)

        return tags
