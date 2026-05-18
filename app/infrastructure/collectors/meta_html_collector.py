import re
from datetime import datetime, timezone

import httpx
from bs4 import BeautifulSoup, NavigableString, Tag

from app.core.logger import get_logger
from app.domain.models.collected_item import CollectedItem
from app.domain.ports.collector import CollectorPort

logger = get_logger(__name__)

BLOG_URL = "https://ai.meta.com/blog/"
BLOG_HREF_RE = re.compile(r"^https://ai\.meta\.com/blog/[^?#]+$")
DATE_RE = re.compile(
    r"(January|February|March|April|May|June|July|August|September|October|November|December|"
    r"Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
    r"[\s.]+\d{1,2}[,\s]+\d{4}"
)
DATE_FORMATS = ("%B %d, %Y", "%b %d, %Y", "%B %d. %Y", "%b. %d, %Y", "%B %d %Y")

KEYWORD_TAGS: dict[str, str] = {
    "llama": "llama",
    "multimodal": "multimodal",
    "reasoning": "reasoning",
    "vision": "vision",
    "audio": "audio",
    "robotics": "robotics",
    "safety": "safety",
    "open-source": "open-source",
    "open source": "open-source",
    "segment anything": "segment-anything",
    "sam": "sam",
}

CTA_TEXTS = {"learn more", "더 알아보기", "read more", "자세히 보기"}


def _keyword_tags(text: str) -> list[str]:
    lower = text.lower()
    return [tag for keyword, tag in KEYWORD_TAGS.items() if keyword in lower]


class MetaHtmlCollector(CollectorPort):
    async def collect(self) -> list[CollectedItem]:
        logger.info("Collecting from Meta AI Blog: %s", BLOG_URL)

        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=20.0,
            headers={"User-Agent": "Mozilla/5.0"},
        ) as client:
            response = await client.get(BLOG_URL)
            response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        # 모든 블로그 포스트 URL 수집 (중복 제거)
        all_blog_anchors = soup.find_all("a", href=BLOG_HREF_RE)
        if not all_blog_anchors:
            logger.warning("No blog anchors found — Meta AI HTML structure may have changed")

        unique_urls: list[str] = []
        seen: set[str] = set()
        for a in all_blog_anchors:
            url = a["href"]
            if url not in seen:
                seen.add(url)
                unique_urls.append(url)

        items: list[CollectedItem] = []
        for url in unique_urls:
            anchors = soup.find_all("a", href=url)
            item = self._parse_card(url, anchors)
            if item:
                items.append(item)

        logger.info("Collected %d items from Meta AI Blog", len(items))
        return items

    def _parse_card(self, url: str, anchors: list[Tag]) -> CollectedItem | None:
        title = self._extract_title(anchors)
        if not title:
            return None

        container = self._find_container(anchors)
        published_at = self._extract_date(container)
        summary = self._extract_summary(container, title)
        category = self._extract_category(container, title)
        tags = self._build_tags(title, summary, category)

        return CollectedItem(
            source="Meta AI",
            title=title,
            url=url,
            published_at=published_at,
            summary=summary,
            tags=tags,
        )

    def _extract_title(self, anchors: list[Tag]) -> str:
        # 1순위: 텍스트 전용 anchor (이미지 없고 CTA 아닌 것)
        for a in anchors:
            if a.find("img"):
                continue
            text = a.get_text(strip=True)
            if text and text.lower() not in CTA_TEXTS and len(text) > 20:
                return text

        # 2순위: anchor 의 aria-label ("Read [Title]" 형식)
        for a in anchors:
            label: str = a.get("aria-label", "")
            if label.startswith("Read ") and len(label) > 10:
                return label.removeprefix("Read ").strip()

        # 3순위: 가장 가까운 컨테이너 안의 heading (카테고리 라벨 등 짧은 것 제외)
        container = self._find_container(anchors)
        if container:
            for heading in container.find_all(["h1", "h2", "h3", "h4", "h5"]):
                text = heading.get_text(strip=True)
                if len(text) > 20:
                    return text

        return ""

    def _find_container(self, anchors: list[Tag]) -> Tag | None:
        # anchor 들의 공통 부모 중 가장 좁은 카드 컨테이너 (4단계 위)
        for a in anchors:
            node = a.parent
            for _ in range(4):
                if node is None:
                    break
                node = node.parent
            if isinstance(node, Tag) and node.name not in ("html", "body"):
                return node
        return None

    def _extract_date(self, container: Tag | None) -> datetime:
        if container is None:
            return datetime.now(timezone.utc)

        for string in container.strings:
            if not isinstance(string, NavigableString):
                continue
            raw = string.strip()
            if DATE_RE.search(raw):
                # "April 08, 2026" 같은 0-padded day 처리
                raw = re.sub(r"(\w+)\s+0(\d),", r"\1 \2,", raw)
                for fmt in DATE_FORMATS:
                    try:
                        return datetime.strptime(raw, fmt)
                    except ValueError:
                        continue

        logger.warning("Date not found for Meta AI card")
        return datetime.now(timezone.utc)

    def _extract_summary(self, container: Tag | None, title: str) -> str:
        if container is None:
            return ""
        NOISE = {"get the latest from ai at meta in your inbox"}
        # 카드 컨텐츠 전용 div 탐색 (2단계 이하 자식 p 우선 — 인접 카드 내용 유입 방지)
        for depth in (2, 4):
            for p in self._find_shallow(container, "p", depth):
                text = p.get_text(strip=True)
                if text and text != title and len(text) > 30 and text.lower() not in NOISE:
                    return text
        return ""

    def _find_shallow(self, root: Tag, tag: str, max_depth: int) -> list[Tag]:
        results: list[Tag] = []
        self._dfs(root, tag, 0, max_depth, results)
        return results

    def _dfs(self, node: Tag, tag: str, depth: int, max_depth: int, results: list[Tag]) -> None:
        if depth > max_depth:
            return
        for child in node.children:
            if not isinstance(child, Tag):
                continue
            if child.name == tag:
                results.append(child)
            self._dfs(child, tag, depth + 1, max_depth, results)

    def _extract_category(self, container: Tag | None, title: str) -> str:
        if container is None:
            return ""
        EXCLUDED = {
            "featured", "learn more", "더 알아보기", "블로그", "blog",
            "the latest ai news from meta", "latest news",
        }
        for p in container.find_all("p"):
            text = p.get_text(strip=True)
            if (
                text
                and len(text) < 40
                and text != title
                and text.lower() not in EXCLUDED
                and not DATE_RE.search(text)
            ):
                return text
        return ""

    def _build_tags(self, title: str, summary: str, category: str) -> list[str]:
        tags = ["meta"]
        combined = f"{title} {summary}".lower()
        tags.extend(_keyword_tags(combined))
        if category and category.lower() not in ("meta", "meta ai"):
            cat_slug = category.lower().replace(" ", "-")
            if cat_slug not in tags:
                tags.append(cat_slug)
        return tags
