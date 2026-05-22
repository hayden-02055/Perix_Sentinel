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
    metadata    TEXT    NOT NULL DEFAULT '{}',
    score       INTEGER NOT NULL DEFAULT 0,
    importance  TEXT    NOT NULL DEFAULT 'normal',
    reason      TEXT    NOT NULL DEFAULT '',
    is_briefed  INTEGER NOT NULL DEFAULT 0,
    briefed_at  TEXT,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
)
"""

MIGRATIONS: list[str] = [
    "ALTER TABLE collected_items ADD COLUMN metadata TEXT NOT NULL DEFAULT '{}'",
    "ALTER TABLE collected_items ADD COLUMN score INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE collected_items ADD COLUMN importance TEXT NOT NULL DEFAULT 'normal'",
    "ALTER TABLE collected_items ADD COLUMN reason TEXT NOT NULL DEFAULT ''",
    "ALTER TABLE collected_items ADD COLUMN is_briefed INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE collected_items ADD COLUMN briefed_at TEXT",
]

SELECT_COLUMNS = (
    "id, source, title, url, url_hash, summary, published_at, tags, metadata, "
    "score, importance, reason, is_briefed, briefed_at"
)


def _db_path() -> str:
    return settings.database_url.replace("sqlite+aiosqlite:///", "")


def _row_to_item(row: tuple) -> CollectedItem:
    (
        _item_id,
        source,
        title,
        url,
        url_hash,
        summary,
        published_at,
        tags,
        metadata,
        score,
        importance,
        reason,
        is_briefed,
        briefed_at,
    ) = row
    return CollectedItem(
        source=source,
        title=title,
        url=url,
        url_hash=url_hash,
        summary=summary,
        published_at=datetime.fromisoformat(published_at),
        tags=json.loads(tags) if tags else [],
        metadata=json.loads(metadata) if metadata else {},
        score=score or 0,
        importance=importance or "normal",
        reason=reason or "",
        is_briefed=bool(is_briefed),
        briefed_at=datetime.fromisoformat(briefed_at) if briefed_at else None,
    )


class SqliteItemRepository(ItemRepositoryPort):
    async def init_db(self) -> None:
        async with aiosqlite.connect(_db_path()) as db:
            await db.execute(CREATE_TABLE_SQL)
            for sql in MIGRATIONS:
                try:
                    await db.execute(sql)
                except Exception:
                    pass  # column already exists
            await db.commit()
        logger.info("SQLite DB initialized")

    async def save(self, item: CollectedItem) -> int | None:
        async with aiosqlite.connect(_db_path()) as db:
            cursor = await db.execute(
                """
                INSERT OR IGNORE INTO collected_items
                    (source, title, url, url_hash, summary, published_at, tags, metadata,
                     score, importance, reason, is_briefed, briefed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item.source,
                    item.title,
                    item.url,
                    item.url_hash,
                    item.summary,
                    item.published_at.isoformat(),
                    json.dumps(item.tags),
                    json.dumps(item.metadata),
                    item.score,
                    item.importance,
                    item.reason,
                    1 if item.is_briefed else 0,
                    item.briefed_at.isoformat() if item.briefed_at else None,
                ),
            )
            await db.commit()
            if cursor.lastrowid and cursor.rowcount:
                return int(cursor.lastrowid)
            # Row already existed (INSERT OR IGNORE skipped it) — look up its id
            async with db.execute(
                "SELECT id FROM collected_items WHERE url_hash = ?", (item.url_hash,)
            ) as lookup:
                row = await lookup.fetchone()
                return int(row[0]) if row else None

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
                f"SELECT {SELECT_COLUMNS} FROM collected_items WHERE summary = ''"
            ) as cursor:
                rows = await cursor.fetchall()
        return [_row_to_item(row) for row in rows]

    async def get_by_id(self, item_id: int) -> CollectedItem | None:
        async with aiosqlite.connect(_db_path()) as db:
            async with db.execute(
                f"SELECT {SELECT_COLUMNS} FROM collected_items WHERE id = ?",
                (item_id,),
            ) as cursor:
                row = await cursor.fetchone()
        return _row_to_item(row) if row else None

    async def mark_briefed(self, item_id: int) -> None:
        async with aiosqlite.connect(_db_path()) as db:
            await db.execute(
                "UPDATE collected_items SET is_briefed = 1, briefed_at = ? WHERE id = ?",
                (datetime.utcnow().isoformat(), item_id),
            )
            await db.commit()
