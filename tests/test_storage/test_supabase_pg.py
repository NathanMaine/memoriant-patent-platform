import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from core.storage.supabase_pg import SupabaseStorage
from core.models.patent import SearchResult, SearchStrategy, Inventor, Assignee


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


@pytest.mark.asyncio
async def test_initialize_creates_pool():
    with patch("core.storage.supabase_pg.asyncpg") as mock_asyncpg:
        mock_pool = MagicMock()
        mock_asyncpg.create_pool = AsyncMock(return_value=mock_pool)
        storage = SupabaseStorage(dsn="postgresql://test:test@localhost/test")
        await storage.initialize()
        mock_asyncpg.create_pool.assert_called_once_with("postgresql://test:test@localhost/test")
        assert storage._pool is mock_pool


@pytest.mark.asyncio
async def test_close_calls_pool_close():
    with patch("core.storage.supabase_pg.asyncpg"):
        storage = SupabaseStorage(dsn="postgresql://test:test@localhost/test")
        mock_pool = AsyncMock()
        storage._pool = mock_pool
        await storage.close()
        mock_pool.close.assert_called_once()


@pytest.mark.asyncio
async def test_close_with_no_pool():
    storage = SupabaseStorage(dsn="postgresql://test:test@localhost/test")
    # _pool is None — should not raise
    await storage.close()


@pytest.mark.asyncio
async def test_save_search_result(supabase_storage):
    storage, mock_conn = supabase_storage
    mock_conn.execute = AsyncMock()

    result = SearchResult(
        patent_id="US11234567",
        title="Novel Invention",
        abstract="A useful abstract.",
        inventors=[Inventor(first="Jane", last="Doe")],
        assignees=[Assignee(organization="Acme Corp")],
        cpc_codes=["G06F 40/30"],
        relevance_score=0.92,
        relevance_notes="Highly relevant",
        provider="google_patents",
        strategy=SearchStrategy.KEYWORD,
    )

    result_id = await storage.save_search_result("project-abc", result)
    assert result_id == str(result.id)
    mock_conn.execute.assert_called_once()
