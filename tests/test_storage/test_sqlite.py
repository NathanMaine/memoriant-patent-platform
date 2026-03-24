import pytest
from uuid import uuid4
from core.storage.sqlite import SQLiteStorage
from core.models.patent import SearchResult, SearchStrategy


@pytest.fixture
async def storage(tmp_path):
    db_path = str(tmp_path / "test.db")
    s = SQLiteStorage(db_path)
    await s.initialize()
    yield s
    await s.close()


@pytest.mark.asyncio
async def test_save_and_get_project(storage):
    project_id = await storage.create_project(
        user_id=str(uuid4()),
        title="Test Invention",
        description="A system for testing",
    )
    assert project_id is not None
    project = await storage.get_project(project_id)
    assert project["title"] == "Test Invention"


@pytest.mark.asyncio
async def test_save_and_list_search_results(storage):
    user_id = str(uuid4())
    project_id = await storage.create_project(
        user_id=user_id,
        title="Test",
        description="Test",
    )
    sr = SearchResult(
        patent_id="US11234567",
        title="TEST PATENT",
        provider="patentsview",
        strategy=SearchStrategy.KEYWORD,
    )
    await storage.save_search_result(project_id, sr)
    results = await storage.list_search_results(project_id)
    assert len(results) == 1
    assert results[0]["patent_id"] == "US11234567"


@pytest.mark.asyncio
async def test_project_not_found(storage):
    project = await storage.get_project(str(uuid4()))
    assert project is None
