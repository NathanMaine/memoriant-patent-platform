import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from core.storage.supabase_pg import SupabaseStorage


@pytest.fixture
def supabase_storage():
    with patch("core.storage.supabase_pg.asyncpg") as mock_asyncpg:
        mock_pool = MagicMock()
        mock_asyncpg.create_pool = AsyncMock(return_value=mock_pool)
        storage = SupabaseStorage(dsn="postgresql://test:test@localhost/test")
        storage._pool = mock_pool

        # Mock pool.acquire() as an async context manager
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=None)
        mock_conn.fetch = AsyncMock(return_value=[])

        context_manager = AsyncMock()
        context_manager.__aenter__ = AsyncMock(return_value=mock_conn)
        context_manager.__aexit__ = AsyncMock(return_value=None)
        mock_pool.acquire.return_value = context_manager

        yield storage, mock_conn


@pytest.mark.asyncio
async def test_create_project(supabase_storage):
    storage, mock_conn = supabase_storage

    project_id = await storage.create_project(
        user_id="user-123", title="Test", description="Test invention"
    )
    # Returns a UUID string (generated internally)
    assert len(project_id) == 36
    mock_conn.execute.assert_called_once()


@pytest.mark.asyncio
async def test_get_project_not_found(supabase_storage):
    storage, mock_conn = supabase_storage
    mock_conn.fetchrow = AsyncMock(return_value=None)

    result = await storage.get_project("nonexistent-id")
    assert result is None


@pytest.mark.asyncio
async def test_list_search_results_empty(supabase_storage):
    storage, mock_conn = supabase_storage
    mock_conn.fetch = AsyncMock(return_value=[])

    results = await storage.list_search_results("project-id")
    assert results == []
