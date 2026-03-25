import pytest
from unittest.mock import patch, MagicMock
from core.storage.registry import StorageRegistry
from core.storage.sqlite import SQLiteStorage
from core.storage.supabase_pg import SupabaseStorage


def test_create_sqlite_backend():
    storage = StorageRegistry.create(backend="sqlite", db_path="/tmp/test.db")
    assert isinstance(storage, SQLiteStorage)
    assert storage._db_path == "/tmp/test.db"


def test_create_sqlite_backend_default_path():
    storage = StorageRegistry.create(backend="sqlite")
    assert isinstance(storage, SQLiteStorage)
    assert "memoriant-patent" in storage._db_path


def test_create_supabase_backend():
    storage = StorageRegistry.create(backend="supabase", dsn="postgresql://test:test@localhost/db")
    assert isinstance(storage, SupabaseStorage)
    assert storage._dsn == "postgresql://test:test@localhost/db"


def test_unknown_backend_raises_value_error():
    with pytest.raises(ValueError, match="Unknown storage backend: redis"):
        StorageRegistry.create(backend="redis")
