from __future__ import annotations
from abc import ABC, abstractmethod
from core.models.patent import SearchResult


class StorageProvider(ABC):
    @abstractmethod
    async def initialize(self) -> None: ...

    @abstractmethod
    async def close(self) -> None: ...

    @abstractmethod
    async def create_project(self, user_id: str, title: str, description: str, **kwargs) -> str: ...

    @abstractmethod
    async def get_project(self, project_id: str) -> dict | None: ...

    @abstractmethod
    async def save_search_result(self, project_id: str, result: SearchResult) -> str: ...

    @abstractmethod
    async def list_search_results(self, project_id: str) -> list[dict]: ...
