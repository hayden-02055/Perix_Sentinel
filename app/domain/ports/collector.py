from abc import ABC, abstractmethod

from app.domain.models.collected_item import CollectedItem


class CollectorPort(ABC):
    @abstractmethod
    async def collect(self) -> list[CollectedItem]:
        ...
