from app.core.datetime_utils import parse_date
from app.core.logger import get_logger
from app.domain.models.collected_item import CollectedItem
from app.domain.ports.collector import CollectorPort
from app.infrastructure.http.async_client import fetch_json

logger = get_logger(__name__)

HF_TRENDING_URL = "https://huggingface.co/api/trending?type=model"

_AUTO_TAGS: list[tuple[str, str]] = [
    ("llama", "llama"),
    ("mixtral", "mixtral"),
    ("mistral", "mistral"),
    ("gemma", "gemma"),
    ("qwen", "qwen"),
    ("phi", "phi"),
    ("gguf", "gguf"),
    ("vision", "vision"),
    ("audio", "audio"),
]

_PIPELINE_TAG_MAP: dict[str, str] = {
    "text-generation": "llm",
    "text2text-generation": "llm",
    "image-to-text": "multimodal",
    "text-to-image": "multimodal",
    "automatic-speech-recognition": "audio",
    "text-to-speech": "audio",
}


def _build_tags(model_id: str, pipeline_tag: str | None, raw_tags: list[str]) -> list[str]:
    tags = ["huggingface"]

    if pipeline_tag:
        tags.append(pipeline_tag)
        extra = _PIPELINE_TAG_MAP.get(pipeline_tag)
        if extra:
            tags.append(extra)

    model_lower = model_id.lower()
    for keyword, tag in _AUTO_TAGS:
        if keyword in model_lower and tag not in tags:
            tags.append(tag)

    for t in raw_tags:
        if t and t not in tags:
            tags.append(t)

    return tags


def _parse_updated_at(model: dict):
    raw = model.get("lastModified") or model.get("updatedAt") or model.get("createdAt") or ""
    return parse_date(raw)


class HuggingFaceApiCollector(CollectorPort):
    async def collect(self) -> list[CollectedItem]:
        logger.info("Collecting from HuggingFace Trending API: %s", HF_TRENDING_URL)

        payload = await fetch_json(HF_TRENDING_URL)
        # API returns {"recentlyTrending": [{repoData: {...}}, ...]}
        data: list[dict] = payload.get("recentlyTrending", []) if isinstance(payload, dict) else payload

        items: list[CollectedItem] = []
        for entry in data:
            model = entry.get("repoData") or entry
            model_id: str = model.get("id") or model.get("modelId") or ""
            if not model_id:
                continue

            author = model_id.split("/")[0] if "/" in model_id else model.get("author", "")
            pipeline_tag: str | None = model.get("pipeline_tag")
            raw_tags: list[str] = model.get("tags") or []
            likes: int = model.get("likes", 0)
            downloads: int = model.get("downloads", 0)
            updated_at = _parse_updated_at(model)

            url = f"https://huggingface.co/{model_id}"
            tags = _build_tags(model_id, pipeline_tag, raw_tags)

            items.append(
                CollectedItem(
                    source="HuggingFace",
                    title=model_id,
                    url=url,
                    published_at=updated_at,
                    summary=f"Trending HuggingFace model by {author}",
                    tags=tags,
                    metadata={
                        "likes": likes,
                        "downloads": downloads,
                        "pipeline_tag": pipeline_tag or "",
                        "author": author,
                    },
                )
            )

        logger.info("Collected %d trending models from HuggingFace", len(items))
        return items
