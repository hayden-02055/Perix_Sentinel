"""Structural test for the Event model + SqliteEventRepository (A1 scope).

No clustering logic is exercised here (that is A2, deferred pending real
ground-truth pairs per docs/notes/clusterer-event-a0-observation.md). This
only pins the schema, JSON round-trip of members/entities, and the upsert
idempotency the SDD's event_id design (md5 of origin url_hash) relies on.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.core.config import settings
from app.domain.models.event import Event, EventMember
from app.infrastructure.repositories.sqlite_event_repository import SqliteEventRepository


@pytest.fixture
async def repo(tmp_path, monkeypatch):
    db_file = tmp_path / "events_test.db"
    monkeypatch.setattr(settings, "database_url", f"sqlite+aiosqlite:///{db_file}")
    r = SqliteEventRepository()
    await r.init_db()
    return r


def _make_event(event_id: str = "abc123") -> Event:
    occurred_at = datetime(2026, 7, 21, 9, 0, tzinfo=timezone.utc)
    return Event(
        title="OpenAI introduces GPT-5.5 agents",
        occurred_at=occurred_at,
        members=[
            EventMember(
                item_id="1",
                role="origin",
                source="OpenAI",
                title="Introducing GPT-5.5 agents",
                url="https://openai.com/blog/gpt-5-5-agents",
                published_at=occurred_at,
            ),
            EventMember(
                item_id="2",
                role="echo",
                source="TechCrunch",
                title="OpenAI launches GPT-5.5 with agentic tooling",
                url="https://techcrunch.com/gpt-5-5",
                published_at=datetime(2026, 7, 21, 14, 0, tzinfo=timezone.utc),
            ),
        ],
        entities={"org": ["openai"], "model": ["gpt5.5"]},
        echo_count=1,
        diversity=1,
        score=23,
        event_id=event_id,
    )


@pytest.mark.asyncio
async def test_upsert_and_get_by_id_round_trip(repo):
    event = _make_event()
    await repo.upsert(event)

    fetched = await repo.get_by_id(event.event_id)

    assert fetched is not None
    assert fetched.event_id == event.event_id
    assert fetched.title == event.title
    assert fetched.occurred_at == event.occurred_at
    assert fetched.echo_count == 1
    assert fetched.diversity == 1
    assert fetched.score == 23
    assert fetched.entities == {"org": ["openai"], "model": ["gpt5.5"]}
    assert len(fetched.members) == 2
    assert fetched.members[0].role == "origin"
    assert fetched.members[1].role == "echo"
    assert fetched.members[1].source == "TechCrunch"
    assert fetched.is_briefed is False


@pytest.mark.asyncio
async def test_upsert_is_idempotent_by_event_id(repo):
    event = _make_event(event_id="same-id")
    await repo.upsert(event)

    event.echo_count = 2
    event.diversity = 2
    await repo.upsert(event)

    fetched = await repo.get_by_id("same-id")
    assert fetched.echo_count == 2
    assert fetched.diversity == 2


@pytest.mark.asyncio
async def test_mark_briefed_sets_flag_and_timestamp(repo):
    event = _make_event(event_id="to-brief")
    await repo.upsert(event)

    await repo.mark_briefed("to-brief")

    fetched = await repo.get_by_id("to-brief")
    assert fetched.is_briefed is True
    assert fetched.briefed_at is not None


@pytest.mark.asyncio
async def test_get_by_id_returns_none_when_missing(repo):
    assert await repo.get_by_id("does-not-exist") is None
