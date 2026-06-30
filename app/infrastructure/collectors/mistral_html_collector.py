import re

from bs4 import BeautifulSoup

from app.core.datetime_utils import parse_date
from app.core.logger import get_logger
from app.domain.models.collected_item import CollectedItem
from app.domain.ports.collector import CollectorPort
from app.infrastructure.http.async_client import fetch_html

logger = get_logger(__name__)

BASE_URL = "https://mistral.ai"
NEWS_URL = f"{BASE_URL}/news/"

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


def _extract_posts(script_content: str) -> list[dict] | None:
    """Next.js __next_f.push 스크립트에서 posts 배열을 추출한다."""
    m = re.search(r'push\(\[1,"(.*?)(?<!\\)"\]\)', script_content, re.DOTALL)
    if not m:
        return None

    inner = m.group(1)
    # JS 문자열 이스케이프 해제 (unicode_escape + UTF-8 복원)
    try:
        decoded = (
            bytes(inner, "utf-8")
            .decode("unicode_escape")
            .encode("latin-1")
            .decode("utf-8")
        )
    except (UnicodeDecodeError, UnicodeEncodeError):
        decoded = bytes(inner, "utf-8").decode("unicode_escape")

    marker = '"posts":['
    idx = decoded.find(marker)
    if idx == -1:
        return None

    start = decoded.index("[", idx)
    depth, in_str, i, end = 0, False, start, start

    while i < len(decoded):
        c = decoded[i]
        if in_str:
            if c == "\\" and i + 1 < len(decoded):
                i += 2
                continue
            if c == '"':
                in_str = False
        else:
            if c == '"':
                in_str = True
            elif c == "[":
                depth += 1
            elif c == "]":
                depth -= 1
                if depth == 0:
                    end = i
                    break
        i += 1

    import json
    try:
        return json.loads(decoded[start : end + 1])
    except Exception as exc:
        logger.warning("Failed to parse Mistral posts JSON: %s", exc)
        return None


class MistralHtmlCollector(CollectorPort):
    async def collect(self) -> list[CollectedItem]:
        logger.info("Collecting from Mistral AI News: %s", NEWS_URL)

        soup = await fetch_html(NEWS_URL)

        posts_raw: list[dict] | None = None
        for script in soup.find_all("script"):
            if not script.string or "posts" not in script.string or "slug" not in script.string:
                continue
            posts_raw = _extract_posts(script.string)
            if posts_raw:
                break

        if not posts_raw:
            logger.warning("No posts found — Mistral AI page structure may have changed")
            return []

        items: list[CollectedItem] = []
        seen_urls: set[str] = set()

        for post in posts_raw:
            slug = post.get("slug", "")
            if not slug:
                continue

            url = f"{BASE_URL}/news/{slug}"
            if url in seen_urls:
                continue
            seen_urls.add(url)

            title: str = post.get("title", "").strip()
            if not title:
                continue

            description: str = (post.get("description") or "").strip()
            date_str: str = post.get("date", "")
            category_name: str = (post.get("category") or {}).get("name", "")

            published_at = parse_date(date_str)
            tags = self._build_tags(title, description, category_name)

            items.append(
                CollectedItem(
                    source="Mistral AI",
                    title=title,
                    url=url,
                    published_at=published_at,
                    summary=description,
                    tags=tags,
                )
            )

        logger.info("Collected %d items from Mistral AI News", len(items))
        return items

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
