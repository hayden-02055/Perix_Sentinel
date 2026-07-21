import json
from datetime import datetime

import aiosqlite

from app.core.config import settings
from app.core.datetime_utils import now_utc
from app.core.logger import get_logger
from app.domain.models.event import Event, EventMember
from app.domain.ports.event_repository import EventRepositoryPort

logger = get_logger(__name__)

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS events (
    event_id     TEXT PRIMARY KEY,
    title        TEXT NOT NULL,
    occurred_at  TEXT NOT NULL,
    members      TEXT NOT NULL,
    entities     TEXT NOT NULL,
    echo_count   INTEGER DEFAULT 0,
    diversity    INTEGER DEFAULT 0,
    score        INTEGER DEFAULT 0,
    importance   TEXT DEFAULT 'normal',
    is_briefed   INTEGER DEFAULT 0,
    briefed_at   TEXT
)
"""

CREATE_INDEX_SQL = [
    "CREATE INDEX IF NOT EXISTS idx_events_occurred ON events(occurred_at)",
    "CREATE INDEX IF NOT EXISTS idx_events_briefed  ON events(is_briefed)",
]

SELECT_COLUMNS = (
    "event_id, title, occurred_at, members, entities, "
    "echo_count, diversity, score, importance, is_briefed, briefed_at"
)


def _db_path() -> str:
    return settings.database_url.replace("sqlite+aiosqlite:///", "")


def _member_to_dict(member: EventMember) -> dict:
    return {
        "item_hash": member.item_hash,
        "role": member.role,
        "source": member.source,
        "title": member.title,
        "url": member.url,
        "published_at": member.published_at.isoformat(),
    }


def _dict_to_member(data: dict) -> EventMember:
    return EventMember(
        item_hash=data["item_hash"],
        role=data["role"],
        source=data["source"],
        title=data["title"],
        url=data["url"],
        published_at=datetime.fromisoformat(data["published_at"]),
    )


def _row_to_event(row: tuple) -> Event:
    (
        event_id,
        title,
        occurred_at,
        members,
        entities,
        echo_count,
        diversity,
        score,
        importance,
        is_briefed,
        briefed_at,
    ) = row
    return Event(
        event_id=event_id,
        title=title,
        occurred_at=datetime.fromisoformat(occurred_at),
        members=[_dict_to_member(m) for m in json.loads(members)] if members else [],
        entities=json.loads(entities) if entities else {},
        echo_count=echo_count or 0,
        diversity=diversity or 0,
        score=score or 0,
        importance=importance or "normal",
        is_briefed=bool(is_briefed),
        briefed_at=datetime.fromisoformat(briefed_at) if briefed_at else None,
    )


class SqliteEventRepository(EventRepositoryPort):
    async def init_db(self) -> None:
        async with aiosqlite.connect(_db_path()) as db:
            await db.execute(CREATE_TABLE_SQL)
            for sql in CREATE_INDEX_SQL:
                await db.execute(sql)
            await db.commit()
        logger.info("SQLite events table initialized")

    async def upsert(self, event: Event) -> None:
        if not event.event_id:
            raise ValueError("Event.event_id must not be empty")
        async with aiosqlite.connect(_db_path()) as db:
            await db.execute(
                """
                INSERT INTO events
                    (event_id, title, occurred_at, members, entities,
                     echo_count, diversity, score, importance, is_briefed, briefed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(event_id) DO UPDATE SET
                    title=excluded.title,
                    occurred_at=excluded.occurred_at,
                    members=excluded.members,
                    entities=excluded.entities,
                    echo_count=excluded.echo_count,
                    diversity=excluded.diversity,
                    score=excluded.score,
                    importance=excluded.importance,
                    is_briefed=CASE WHEN events.is_briefed = 1 THEN 1 ELSE excluded.is_briefed END,
                    briefed_at=CASE WHEN events.briefed_at IS NOT NULL THEN events.briefed_at ELSE excluded.briefed_at END
                """,
                (
                    event.event_id,
                    event.title,
                    event.occurred_at.isoformat(),
                    json.dumps([_member_to_dict(m) for m in event.members]),
                    json.dumps(event.entities),
                    event.echo_count,
                    event.diversity,
                    event.score,
                    event.importance,
                    1 if event.is_briefed else 0,
                    event.briefed_at.isoformat() if event.briefed_at else None,
                ),
            )
            await db.commit()

    async def get_by_id(self, event_id: str) -> Event | None:
        async with aiosqlite.connect(_db_path()) as db:
            async with db.execute(
                f"SELECT {SELECT_COLUMNS} FROM events WHERE event_id = ?", (event_id,)
            ) as cursor:
                row = await cursor.fetchone()
        return _row_to_event(row) if row else None

    async def mark_briefed(self, event_id: str) -> None:
        async with aiosqlite.connect(_db_path()) as db:
            await db.execute(
                "UPDATE events SET is_briefed = 1, briefed_at = ? WHERE event_id = ?",
                (now_utc().isoformat(), event_id),
            )
            await db.commit()
