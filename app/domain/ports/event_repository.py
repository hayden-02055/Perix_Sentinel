from abc import ABC, abstractmethod

from app.domain.models.event import Event


class EventRepositoryPort(ABC):
    @abstractmethod
    async def upsert(self, event: Event) -> None:
        ...

    @abstractmethod
    async def get_by_id(self, event_id: str) -> Event | None:
        ...

    @abstractmethod
    async def mark_briefed(self, event_id: str) -> None:
        ...
