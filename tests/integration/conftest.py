import pytest
import os
import asyncio

PATENTSVIEW_API_KEY = os.getenv("PATENTSVIEW_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

skip_no_patentsview = pytest.mark.skipif(
    not PATENTSVIEW_API_KEY,
    reason="PATENTSVIEW_API_KEY not set"
)
skip_no_anthropic = pytest.mark.skipif(
    not ANTHROPIC_API_KEY,
    reason="ANTHROPIC_API_KEY not set"
)
