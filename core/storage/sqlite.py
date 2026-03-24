from __future__ import annotations
import json
from uuid import uuid4
import aiosqlite
from core.models.patent import SearchResult
from core.storage.base import StorageProvider


class SQLiteStorage(StorageProvider):
    def __init__(self, db_path: str):
        self._db_path = db_path
        self._db: aiosqlite.Connection | None = None

    async def initialize(self) -> None:
        self._db = await aiosqlite.connect(self._db_path)
        self._db.row_factory = aiosqlite.Row
        await self._db.executescript("""
            CREATE TABLE IF NOT EXISTS patent_projects (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                technical_field TEXT,
                filing_format TEXT,
                status TEXT DEFAULT 'draft',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS search_results (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL REFERENCES patent_projects(id),
                provider TEXT NOT NULL,
                patent_id TEXT NOT NULL,
                patent_title TEXT NOT NULL,
                patent_abstract TEXT,
                patent_date TEXT,
                inventors TEXT,
                assignees TEXT,
                cpc_codes TEXT,
                relevance_score REAL,
                relevance_notes TEXT,
                search_strategy TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

    async def close(self) -> None:
        if self._db:
            await self._db.close()

    async def create_project(self, user_id: str, title: str, description: str, **kwargs) -> str:
        project_id = str(uuid4())
        await self._db.execute(
            "INSERT INTO patent_projects (id, user_id, title, description) VALUES (?, ?, ?, ?)",
            (project_id, user_id, title, description),
        )
        await self._db.commit()
        return project_id

    async def get_project(self, project_id: str) -> dict | None:
        cursor = await self._db.execute(
            "SELECT * FROM patent_projects WHERE id = ?", (project_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def save_search_result(self, project_id: str, result: SearchResult) -> str:
        result_id = str(result.id)
        await self._db.execute(
            """INSERT INTO search_results
               (id, project_id, provider, patent_id, patent_title, patent_abstract,
                patent_date, inventors, assignees, cpc_codes, relevance_score,
                relevance_notes, search_strategy)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                result_id, project_id, result.provider, result.patent_id, result.title,
                result.abstract, str(result.patent_date) if result.patent_date else None,
                json.dumps([i.model_dump() for i in result.inventors]),
                json.dumps([a.model_dump() for a in result.assignees]),
                json.dumps(result.cpc_codes),
                result.relevance_score, result.relevance_notes, result.strategy.value,
            ),
        )
        await self._db.commit()
        return result_id

    async def list_search_results(self, project_id: str) -> list[dict]:
        cursor = await self._db.execute(
            "SELECT * FROM search_results WHERE project_id = ? ORDER BY created_at DESC",
            (project_id,),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
