from __future__ import annotations
import structlog
from core.storage.base import StorageProvider
from core.storage.sqlite import SQLiteStorage
from core.storage.supabase_pg import SupabaseStorage

logger = structlog.get_logger(__name__)


class StorageRegistry:
    @staticmethod
    def create(backend: str, **kwargs) -> StorageProvider:
        if backend == "sqlite":
            logger.info("storage.registry.create", backend=backend)
            return SQLiteStorage(db_path=kwargs.get("db_path", "~/.memoriant-patent/data.db"))
        elif backend == "supabase":
            logger.info("storage.registry.create", backend=backend)
            return SupabaseStorage(dsn=kwargs["dsn"])
        else:
            raise ValueError(f"Unknown storage backend: {backend}")
