"""Tests for the examiner statistics module.

Written before implementation (TDD). All tests mock httpx responses
to avoid real network calls against PatentsView.
"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

# ---------------------------------------------------------------------------
# Shared fixtures and sample data
# ---------------------------------------------------------------------------

SAMPLE_EXAMINER_ROW = {
    "patent_examiner_id": "EX001",
    "examiner_name_last": "Smith",
    "examiner_name_first": "John",
    "examiner_art_unit": "3621",
    "examiner_role": "primary",
}

SAMPLE_PATENTSVIEW_RESPONSE = {
    "patents": [
        {
            "examiners": [SAMPLE_EXAMINER_ROW],
            "patent_id": "US10000001",
            "patent_date": "2020-01-01",
        },
        {
            "examiners": [SAMPLE_EXAMINER_ROW],
            "patent_id": "US10000002",
            "patent_date": "2020-02-01",
        },
    ],
    "count": 2,
    "total_patent_count": 2,
}

EMPTY_PATENTSVIEW_RESPONSE = {
    "patents": [],
    "count": 0,
    "total_patent_count": 0,
}


def _make_mock_response(status_code: int, body: dict) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = body
    resp.text = json.dumps(body)
    return resp


def _make_async_client(mock_response: MagicMock) -> MagicMock:
    client = MagicMock()
    client.get = AsyncMock(return_value=mock_response)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return client


# ---------------------------------------------------------------------------
# Import guard
# ---------------------------------------------------------------------------


def test_examiner_stats_module_importable():
    """The module must import without errors."""
    import core.analysis.examiner_stats  # noqa: F401


# ---------------------------------------------------------------------------
# ExaminerStats model
# ---------------------------------------------------------------------------


class TestExaminerStatsModel:
    def test_model_fields(self):
        from core.analysis.examiner_stats import ExaminerStats

        stats = ExaminerStats(
            examiner_name="John Smith",
            examiner_id="EX001",
            art_unit="3621",
            allowance_rate=0.65,
            total_applications=200,
            avg_office_actions=1.8,
            specialties=["machine learning", "data processing"],
        )
        assert stats.examiner_name == "John Smith"
        assert stats.examiner_id == "EX001"
        assert stats.art_unit == "3621"
        assert stats.allowance_rate == 0.65
        assert stats.total_applications == 200
        assert stats.avg_office_actions == 1.8
        assert "machine learning" in stats.specialties

    def test_allowance_rate_between_zero_and_one(self):
        from core.analysis.examiner_stats import ExaminerStats

        stats = ExaminerStats(
            examiner_name="Jane Doe",
            examiner_id="EX002",
            art_unit="3622",
            allowance_rate=0.0,
            total_applications=10,
            avg_office_actions=2.0,
            specialties=[],
        )
        assert 0.0 <= stats.allowance_rate <= 1.0

    def test_specialties_defaults_to_empty_list(self):
        from core.analysis.examiner_stats import ExaminerStats

        stats = ExaminerStats(
            examiner_name="Test Examiner",
            examiner_id="EX003",
            art_unit="3623",
            allowance_rate=0.5,
            total_applications=50,
            avg_office_actions=1.5,
        )
        assert stats.specialties == []


# ---------------------------------------------------------------------------
# get_examiner_stats
# ---------------------------------------------------------------------------


class TestGetExaminerStats:
    @pytest.mark.asyncio
    async def test_returns_list_of_examiner_stats(self):
        from core.analysis.examiner_stats import get_examiner_stats

        mock_resp = _make_mock_response(200, SAMPLE_PATENTSVIEW_RESPONSE)
        mock_client = _make_async_client(mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await get_examiner_stats(art_unit="3621", api_key="test-key")

        assert isinstance(result, list)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_returns_examiner_stats_instances(self):
        from core.analysis.examiner_stats import get_examiner_stats, ExaminerStats

        mock_resp = _make_mock_response(200, SAMPLE_PATENTSVIEW_RESPONSE)
        mock_client = _make_async_client(mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await get_examiner_stats(art_unit="3621", api_key="test-key")

        for item in result:
            assert isinstance(item, ExaminerStats)

    @pytest.mark.asyncio
    async def test_empty_art_unit_returns_empty_list(self):
        from core.analysis.examiner_stats import get_examiner_stats

        mock_resp = _make_mock_response(200, EMPTY_PATENTSVIEW_RESPONSE)
        mock_client = _make_async_client(mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await get_examiner_stats(art_unit="9999", api_key="test-key")

        assert result == []

    @pytest.mark.asyncio
    async def test_api_error_raises_runtime_error(self):
        from core.analysis.examiner_stats import get_examiner_stats

        mock_resp = _make_mock_response(403, {"error": "Forbidden"})
        mock_client = _make_async_client(mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(RuntimeError, match="PatentsView"):
                await get_examiner_stats(art_unit="3621", api_key="bad-key")

    @pytest.mark.asyncio
    async def test_network_error_raises_runtime_error(self):
        from core.analysis.examiner_stats import get_examiner_stats

        mock_client = MagicMock()
        mock_client.get = AsyncMock(
            side_effect=httpx.RequestError("network failure")
        )
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(RuntimeError, match="network"):
                await get_examiner_stats(art_unit="3621", api_key="test-key")


# ---------------------------------------------------------------------------
# lookup_examiner
# ---------------------------------------------------------------------------


class TestLookupExaminer:
    @pytest.mark.asyncio
    async def test_lookup_returns_single_examiner_stats(self):
        from core.analysis.examiner_stats import lookup_examiner, ExaminerStats

        mock_resp = _make_mock_response(200, SAMPLE_PATENTSVIEW_RESPONSE)
        mock_client = _make_async_client(mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await lookup_examiner(examiner_id="EX001", api_key="test-key")

        assert isinstance(result, ExaminerStats)
        assert result.examiner_id == "EX001"

    @pytest.mark.asyncio
    async def test_lookup_not_found_raises_value_error(self):
        from core.analysis.examiner_stats import lookup_examiner

        mock_resp = _make_mock_response(200, EMPTY_PATENTSVIEW_RESPONSE)
        mock_client = _make_async_client(mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(ValueError, match="not found"):
                await lookup_examiner(examiner_id="NOPE", api_key="test-key")

    @pytest.mark.asyncio
    async def test_lookup_api_error_raises_runtime_error(self):
        from core.analysis.examiner_stats import lookup_examiner

        mock_resp = _make_mock_response(500, {"error": "Server Error"})
        mock_client = _make_async_client(mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(RuntimeError, match="PatentsView"):
                await lookup_examiner(examiner_id="EX001", api_key="test-key")

    @pytest.mark.asyncio
    async def test_lookup_network_error_raises_runtime_error(self):
        from core.analysis.examiner_stats import lookup_examiner

        mock_client = MagicMock()
        mock_client.get = AsyncMock(
            side_effect=httpx.RequestError("network failure")
        )
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(RuntimeError, match="network"):
                await lookup_examiner(examiner_id="EX001", api_key="test-key")

    @pytest.mark.asyncio
    async def test_lookup_examiner_id_not_in_aggregated(self):
        """Covers the branch where patents exist but examiner_id not in aggregated dict."""
        from core.analysis.examiner_stats import lookup_examiner

        # Return a patent where the examiner has a DIFFERENT id than what we look up
        response_with_different_examiner = {
            "patents": [
                {
                    "examiners": [
                        {
                            "patent_examiner_id": "OTHER001",
                            "examiner_name_last": "Doe",
                            "examiner_name_first": "Jane",
                            "patent_examiner_art_unit": "3621",
                            "patent_examiner_role": "primary",
                        }
                    ],
                    "patent_id": "US10000001",
                    "patent_date": "2020-01-01",
                }
            ],
            "count": 1,
            "total_patent_count": 1,
        }
        mock_resp = _make_mock_response(200, response_with_different_examiner)
        mock_client = _make_async_client(mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(ValueError, match="not found"):
                await lookup_examiner(examiner_id="MISSING_ID", api_key="test-key")

    @pytest.mark.asyncio
    async def test_aggregate_skips_examiner_with_no_id(self):
        """Covers line 81: examiner entry with empty patent_examiner_id is skipped."""
        from core.analysis.examiner_stats import get_examiner_stats

        response_with_no_id = {
            "patents": [
                {
                    "examiners": [
                        {
                            "patent_examiner_id": "",  # empty — should be skipped
                            "examiner_name_last": "Ghost",
                            "examiner_name_first": "No",
                            "patent_examiner_art_unit": "3621",
                        }
                    ],
                    "patent_id": "US10000001",
                }
            ],
            "count": 1,
            "total_patent_count": 1,
        }
        mock_resp = _make_mock_response(200, response_with_no_id)
        mock_client = _make_async_client(mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await get_examiner_stats(art_unit="3621", api_key="test-key")

        # The examiner with empty id is skipped → empty list
        assert result == []
