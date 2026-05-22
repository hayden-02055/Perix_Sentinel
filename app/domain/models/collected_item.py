from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class CollectedItem:
    source: str
    title: str
    url: str
    published_at: datetime
    summary: str = ""
    tags: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    url_hash: str = ""

    score: int = 0
    importance: str = "normal"
    reason: str = ""
    is_briefed: bool = False
    briefed_at: datetime | None = None

    def __post_init__(self) -> None:
        if not self.url_hash:
            import hashlib
            self.url_hash = hashlib.md5(self.url.encode()).hexdigest()
