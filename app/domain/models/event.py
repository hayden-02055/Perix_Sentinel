from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class EventMember:
    item_id: str
    role: str  # "origin" | "echo"
    source: str
    title: str
    url: str
    published_at: datetime


@dataclass
class Event:
    title: str
    occurred_at: datetime
    members: list[EventMember] = field(default_factory=list)
    entities: dict = field(default_factory=dict)  # {"org": [...], "model": [...]}
    echo_count: int = 0
    diversity: int = 0
    score: int = 0
    importance: str = "normal"
    is_briefed: bool = False
    briefed_at: datetime | None = None
    event_id: str = ""
