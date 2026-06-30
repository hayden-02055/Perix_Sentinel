from bs4 import Tag

from app.core.datetime_utils import now_utc
from app.core.logger import get_logger
from app.domain.models.collected_item import CollectedItem
from app.domain.ports.collector import CollectorPort
from app.infrastructure.http.async_client import fetch_html

logger = get_logger(__name__)

TRENDING_URL = "https://github.com/trending"
BASE_URL = "https://github.com"

_KEYWORD_TAGS: list[str] = [
    "agent", "rag", "mcp", "llm", "multimodal", "memory",
    "browser", "workflow", "automation", "ai", "gpt", "copilot",
]


def _parse_int(text: str) -> int:
    try:
        return int(text.strip().replace(",", ""))
    except ValueError:
        return 0


def _build_tags(repo_name: str, description: str, language: str | None) -> list[str]:
    tags = ["github"]

    if language:
        tags.append(language.lower())

    combined = f"{repo_name} {description}".lower()
    for keyword in _KEYWORD_TAGS:
        if keyword in combined and keyword not in tags:
            tags.append(keyword)

    return tags


def _parse_article(article: Tag) -> CollectedItem | None:
    repo_link = article.select_one("h2 a")
    if not repo_link:
        logger.warning("Could not find repo link in article; skipping")
        return None

    href = repo_link.get("href", "")
    parts = href.strip("/").split("/")
    if len(parts) < 2:
        logger.warning("Unexpected repo href format: %s", href)
        return None

    owner, repo_name = parts[0], parts[1]
    repo_full = f"{owner}/{repo_name}"
    url = f"{BASE_URL}/{repo_full}"

    desc_el = article.select_one("p")
    description = desc_el.get_text(strip=True) if desc_el else ""

    lang_el = article.select_one('[itemprop="programmingLanguage"]')
    language = lang_el.get_text(strip=True) if lang_el else None

    star_links = article.select('a[href*="/stargazers"]')
    stars = _parse_int(star_links[0].get_text(strip=True)) if star_links else 0

    fork_links = article.select('a[href*="/forks"]')
    forks = _parse_int(fork_links[0].get_text(strip=True)) if fork_links else 0

    stars_today = 0
    for span in article.select("span"):
        text = span.get_text(strip=True)
        if "star" in text.lower() and "today" in text.lower():
            stars_today = _parse_int(text.split()[0])
            break

    tags = _build_tags(repo_full, description, language)

    return CollectedItem(
        source="GitHub Trending",
        title=repo_full,
        url=url,
        published_at=now_utc(),
        summary=description,
        tags=tags,
        metadata={
            "language": language or "",
            "stars": stars,
            "stars_today": stars_today,
            "forks": forks,
        },
    )


class GitHubTrendingCollector(CollectorPort):
    async def collect(self) -> list[CollectedItem]:
        logger.info("Collecting from GitHub Trending: %s", TRENDING_URL)

        soup = await fetch_html(TRENDING_URL)
        articles = soup.select("article.Box-row")

        if not articles:
            logger.warning("No trending articles found — GitHub page structure may have changed")
            return []

        items: list[CollectedItem] = []
        for article in articles:
            item = _parse_article(article)
            if item:
                items.append(item)

        logger.info("Collected %d trending repos from GitHub", len(items))
        return items
