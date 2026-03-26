"""SQLite round-trip integration tests.

No external services required — SQLite is always available.
These tests create a real (temporary) database, write data through the
StorageProvider interface, and verify the persisted values match exactly.
"""
from __future__ import annotations

import pytest
from uuid import uuid4

from core.storage.sqlite import SQLiteStorage
from core.models.patent import Inventor, Assignee, SearchResult, SearchStrategy


# ---------------------------------------------------------------------------
# Shared fixture
# ---------------------------------------------------------------------------

@pytest.fixture
async def storage(tmp_path):
    db_path = str(tmp_path / "roundtrip.db")
    s = SQLiteStorage(db_path)
    await s.initialize()
    yield s
    await s.close()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_and_retrieve_project(storage):
    """A project written to SQLite can be read back with identical field values."""
    uid = str(uuid4())
    project_id = await storage.create_project(
        user_id=uid,
        title="Wireless Power Transfer System",
        description="A novel inductive coupling approach for EV charging.",
    )
    assert project_id is not None

    project = await storage.get_project(project_id)
    assert project is not None
    assert project["title"] == "Wireless Power Transfer System"
    assert project["description"] == "A novel inductive coupling approach for EV charging."
    assert project["user_id"] == uid


@pytest.mark.asyncio
async def test_project_id_is_unique_across_inserts(storage):
    """Each create_project call must yield a distinct project ID."""
    uid = str(uuid4())
    id_a = await storage.create_project(user_id=uid, title="Alpha", description="d")
    id_b = await storage.create_project(user_id=uid, title="Beta", description="d")
    assert id_a != id_b


@pytest.mark.asyncio
async def test_get_project_returns_none_for_missing_id(storage):
    """Querying a non-existent project ID must return None, not raise."""
    result = await storage.get_project(str(uuid4()))
    assert result is None


@pytest.mark.asyncio
async def test_save_and_list_search_results_roundtrip(storage):
    """A SearchResult written then retrieved via list_search_results matches the original."""
    uid = str(uuid4())
    project_id = await storage.create_project(
        user_id=uid, title="Test Project", description="desc"
    )

    sr = SearchResult(
        patent_id="US99887766",
        title="ADVANCED BATTERY MANAGEMENT SYSTEM",
        abstract="A system for managing lithium-ion battery packs.",
        inventors=[Inventor(first="Ada", last="Lovelace")],
        assignees=[Assignee(organization="BatteryTech Corp")],
        cpc_codes=["H01M10/42"],
        relevance_score=0.92,
        provider="patentsview",
        strategy=SearchStrategy.KEYWORD,
    )
    saved_id = await storage.save_search_result(project_id, sr)
    assert saved_id == str(sr.id)

    results = await storage.list_search_results(project_id)
    assert len(results) == 1
    row = results[0]
    assert row["patent_id"] == "US99887766"
    assert row["patent_title"] == "ADVANCED BATTERY MANAGEMENT SYSTEM"
    assert row["provider"] == "patentsview"
    assert row["relevance_score"] == pytest.approx(0.92)


@pytest.mark.asyncio
async def test_list_search_results_empty_for_unknown_project(storage):
    """Listing search results for a non-existent project returns an empty list."""
    results = await storage.list_search_results(str(uuid4()))
    assert results == []
