from __future__ import annotations
from core.storage.base import StorageProvider
from core.storage.sqlite import SQLiteStorage
from core.storage.supabase_pg import SupabaseStorage


class StorageRegistry:
    @staticmethod
    def create(backend: str, **kwargs) -> StorageProvider:
        if backend == "sqlite":
            return SQLiteStorage(db_path=kwargs.get("db_path", "~/.memoriant-patent/data.db"))
        elif backend == "supabase":
            return SupabaseStorage(dsn=kwargs["dsn"])
        else:
            raise ValueError(f"Unknown storage backend: {backend}")
