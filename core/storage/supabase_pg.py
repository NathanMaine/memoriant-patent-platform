from __future__ import annotations
import json
from uuid import uuid4
import asyncpg
from core.models.patent import SearchResult
from core.storage.base import StorageProvider


class SupabaseStorage(StorageProvider):
    def __init__(self, dsn: str):
        self._dsn = dsn
        self._pool: asyncpg.Pool | None = None

    async def initialize(self) -> None:
        self._pool = await asyncpg.create_pool(self._dsn)

    async def close(self) -> None:
        if self._pool:
            await self._pool.close()

    async def create_project(self, user_id: str, title: str, description: str, **kwargs) -> str:
        project_id = str(uuid4())
        async with self._pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO patent_projects (id, user_id, title, description)
                   VALUES ($1, $2, $3, $4)""",
                project_id, user_id, title, description,
            )
        return project_id

    async def get_project(self, project_id: str) -> dict | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM patent_projects WHERE id = $1", project_id
            )
        return dict(row) if row else None

    async def save_search_result(self, project_id: str, result: SearchResult) -> str:
        result_id = str(result.id)
        async with self._pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO search_results
                   (id, project_id, provider, patent_id, patent_title, patent_abstract,
                    patent_date, inventors, assignees, cpc_codes, relevance_score,
                    relevance_notes, search_strategy)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13)""",
                result_id, project_id, result.provider, result.patent_id, result.title,
                result.abstract, result.patent_date,
                json.dumps([i.model_dump() for i in result.inventors]),
                json.dumps([a.model_dump() for a in result.assignees]),
                json.dumps(result.cpc_codes),
                result.relevance_score, result.relevance_notes, result.strategy.value,
            )
        return result_id

    async def list_search_results(self, project_id: str) -> list[dict]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM search_results WHERE project_id = $1 ORDER BY created_at DESC",
                project_id,
            )
        return [dict(row) for row in rows]
