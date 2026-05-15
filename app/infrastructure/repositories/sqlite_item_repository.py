import json
from datetime import datetime

import aiosqlite

from app.core.config import settings
from app.core.logger import get_logger
from app.domain.models.collected_item import CollectedItem
from app.domain.ports.repository import ItemRepositoryPort

logger = get_logger(__name__)

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS collected_items (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    source      TEXT    NOT NULL,
    title       TEXT    NOT NULL,
    url         TEXT    NOT NULL,
    url_hash    TEXT    NOT NULL UNIQUE,
    summary     TEXT    NOT NULL DEFAULT '',
    published_at TEXT   NOT NULL,
    tags        TEXT    NOT NULL DEFAULT '[]',
    created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
)
"""


def _db_path() -> str:
    return settings.database_url.replace("sqlite+aiosqlite:///", "")


class SqliteItemRepository(ItemRepositoryPort):
    async def init_db(self) -> None:
        async with aiosqlite.connect(_db_path()) as db:
            await db.execute(CREATE_TABLE_SQL)
            await db.commit()
        logger.info("SQLite DB initialized")

    async def save(self, item: CollectedItem) -> None:
        async with aiosqlite.connect(_db_path()) as db:
            await db.execute(
                """
                INSERT OR IGNORE INTO collected_items
                    (source, title, url, url_hash, summary, published_at, tags)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item.source,
                    item.title,
                    item.url,
                    item.url_hash,
                    item.summary,
                    item.published_at.isoformat(),
                    json.dumps(item.tags),
                ),
            )
            await db.commit()

    async def exists_by_hash(self, url_hash: str) -> bool:
        async with aiosqlite.connect(_db_path()) as db:
            async with db.execute(
                "SELECT COUNT(*) FROM collected_items WHERE url_hash = ?", (url_hash,)
            ) as cursor:
                row = await cursor.fetchone()
                return row[0] > 0

    async def get_unsummarized(self) -> list[CollectedItem]:
        async with aiosqlite.connect(_db_path()) as db:
            async with db.execute(
                "SELECT source, title, url, url_hash, summary, published_at, tags "
                "FROM collected_items WHERE summary = ''"
            ) as cursor:
                rows = await cursor.fetchall()

        return [
            CollectedItem(
                source=row[0],
                title=row[1],
                url=row[2],
                url_hash=row[3],
                summary=row[4],
                published_at=datetime.fromisoformat(row[5]),
                tags=json.loads(row[6]),
            )
            for row in rows
        ]
