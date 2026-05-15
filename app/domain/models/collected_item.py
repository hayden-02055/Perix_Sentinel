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
    url_hash: str = ""

    def __post_init__(self) -> None:
        if not self.url_hash:
            import hashlib
            self.url_hash = hashlib.md5(self.url.encode()).hexdigest()
