from fastapi import APIRouter, HTTPException

from app.domain.models.collected_item import CollectedItem
from app.infrastructure.repositories.sqlite_item_repository import SqliteItemRepository

router = APIRouter()


def _serialize(item: CollectedItem) -> dict:
    return {
        "source": item.source,
        "title": item.title,
        "url": item.url,
        "summary": item.summary,
        "published_at": item.published_at.isoformat(),
        "tags": item.tags,
        "metadata": item.metadata,
        "score": item.score,
        "importance": item.importance,
        "reason": item.reason,
        "is_briefed": item.is_briefed,
        "briefed_at": item.briefed_at.isoformat() if item.briefed_at else None,
    }


@router.get("/items/{item_id}")
async def get_item(item_id: int) -> dict:
    repository = SqliteItemRepository()
    item = await repository.get_by_id(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    return {"id": item_id, **_serialize(item)}
