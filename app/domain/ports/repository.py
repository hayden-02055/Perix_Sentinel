from abc import ABC, abstractmethod

from app.domain.models.collected_item import CollectedItem


class ItemRepositoryPort(ABC):
    @abstractmethod
    async def save(self, item: CollectedItem) -> None:
        ...

    @abstractmethod
    async def exists_by_hash(self, url_hash: str) -> bool:
        ...

    @abstractmethod
    async def get_unsummarized(self) -> list[CollectedItem]:
        ...
