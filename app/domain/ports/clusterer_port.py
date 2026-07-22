"""ClustererPort (SDD §6) — source-agnostic clustering contract.

The active implementation is ``ExactDupClusterer``; the isolated fuzzy slot
(``FuzzyClusterer``) intentionally does *not* implement this port because it
returns the legacy origin/echo ``Event`` shape, not ``PassthroughEvent``.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.models.collected_item import CollectedItem
from app.domain.models.passthrough_event import PassthroughEvent


class ClustererPort(ABC):
    @abstractmethod
    def cluster(self, items: list[CollectedItem]) -> list[PassthroughEvent]:
        ...
