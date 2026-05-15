from abc import ABC, abstractmethod

from app.domain.models.collected_item import CollectedItem


class PublisherPort(ABC):
    @abstractmethod
    async def publish(self, items: list[CollectedItem]) -> None:
        ...
