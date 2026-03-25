from __future__ import annotations

import pytest
from core.embedding.chunker import chunk_patent_text, PatentChunk


# ---------------------------------------------------------------------------
# Abstract chunking
# ---------------------------------------------------------------------------

def test_abstract_returns_single_chunk():
    text = "This invention relates to a novel widget for processing data."
    chunks = chunk_patent_text(text, "abstract")
    assert len(chunks) == 1
    assert chunks[0].text == text
    assert chunks[0].chunk_type == "abstract"
    assert chunks[0].chunk_index == 0


def test_abstract_metadata_present():
    text = "An abstract text."
    chunks = chunk_patent_text(text, "abstract")
    assert isinstance(chunks[0].metadata, dict)


# ---------------------------------------------------------------------------
# Title chunking
# ---------------------------------------------------------------------------

def test_title_returns_single_chunk():
    text = "System and Method for Patent Processing"
    chunks = chunk_patent_text(text, "title")
    assert len(chunks) == 1
    assert chunks[0].text == text
    assert chunks[0].chunk_type == "title"
    assert chunks[0].chunk_index == 0


def test_title_metadata_present():
    text = "A Device for Doing Things"
    chunks = chunk_patent_text(text, "title")
    assert isinstance(chunks[0].metadata, dict)


# ---------------------------------------------------------------------------
# Claim chunking
# ---------------------------------------------------------------------------

def test_claims_split_per_claim():
    text = (
        "1. A method comprising:\n"
        "   performing a step.\n"
        "2. The method of claim 1, further comprising:\n"
        "   performing another step.\n"
        "3. A system comprising:\n"
        "   a component."
    )
    chunks = chunk_patent_text(text, "claim")
    assert len(chunks) == 3
    assert chunks[0].chunk_index == 0
    assert chunks[1].chunk_index == 1
    assert chunks[2].chunk_index == 2
    assert "1. A method" in chunks[0].text
    assert "2. The method" in chunks[1].text
    assert "3. A system" in chunks[2].text


def test_claims_chunk_type_is_claim():
    text = "1. A device.\n2. The device of claim 1."
    chunks = chunk_patent_text(text, "claim")
    for chunk in chunks:
        assert chunk.chunk_type == "claim"


def test_claims_single_claim():
    text = "1. A standalone claim with no dependents."
    chunks = chunk_patent_text(text, "claim")
    assert len(chunks) == 1
    assert chunks[0].text.strip() == text.strip()


# ---------------------------------------------------------------------------
# Description chunking
# ---------------------------------------------------------------------------

def test_description_splits_long_text():
    # ~600 tokens worth of text at ~4 chars/token = ~2400 chars
    # Build a long text with paragraph breaks (double newline = paragraph boundary)
    paragraph = "A " + "word " * 150 + "\n\n"  # ~150 words ~= 150 tokens per para
    text = paragraph * 6  # 6 paragraphs ~ 900 tokens total
    chunks = chunk_patent_text(text, "description")
    # Should produce more than 1 chunk since total > 512 tokens
    assert len(chunks) > 1


def test_description_chunk_size_within_limit():
    # Each paragraph ~200 tokens; 3 paragraphs = 600 tokens -> should split
    para = "word " * 200 + "\n\n"  # ~200 tokens each
    text = para * 3
    chunks = chunk_patent_text(text, "description")
    for chunk in chunks:
        # 512 tokens * 4 chars/token = 2048 chars max (allow slight overflow at paragraph boundary)
        assert len(chunk.text) <= 512 * 4 * 2  # generous upper bound


def test_description_chunk_type():
    para = "x " * 300 + "\n\n"
    text = para * 2
    chunks = chunk_patent_text(text, "description")
    for chunk in chunks:
        assert chunk.chunk_type == "description"


def test_description_chunk_indices_sequential():
    para = "y " * 300 + "\n\n"
    text = para * 4
    chunks = chunk_patent_text(text, "description")
    for i, chunk in enumerate(chunks):
        assert chunk.chunk_index == i


def test_description_overlap_carries_small_paragraph():
    # Design so that (big + small) fits in one chunk (~1690 chars < 2048),
    # but (big + small + big) exceeds the limit (~3300 chars > 2048),
    # triggering a flush. The small paragraph (80 chars) fits in the 64-token
    # overlap window (256 chars), exercising lines 119-120 of chunker.py.
    big_para = "filler " * 230 + "\n\n"    # ~1610 chars, ~402 tokens
    small_para = "overlap " * 10 + "\n\n"  # ~80 chars, fits in overlap budget
    text = big_para + small_para + big_para
    chunks = chunk_patent_text(text, "description")
    assert len(chunks) >= 2
    # The second chunk should contain some text (overlap carried forward)
    assert chunks[1].text.strip() != ""
    # The overlap text should appear in the second chunk
    assert "overlap" in chunks[1].text


def test_description_short_text_single_chunk():
    text = "A short description that fits in one chunk."
    chunks = chunk_patent_text(text, "description")
    assert len(chunks) == 1
    assert chunks[0].text == text


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

def test_empty_text_returns_empty_list():
    for chunk_type in ("abstract", "title", "claim", "description"):
        chunks = chunk_patent_text("", chunk_type)
        assert chunks == [], f"Expected empty list for chunk_type={chunk_type}"


def test_unknown_chunk_type_raises_value_error():
    with pytest.raises(ValueError, match="Unknown chunk_type"):
        chunk_patent_text("Some text", "unknown_type")


# ---------------------------------------------------------------------------
# PatentChunk model
# ---------------------------------------------------------------------------

def test_patent_chunk_is_pydantic_model():
    chunk = PatentChunk(text="hello", chunk_type="abstract", chunk_index=0, metadata={})
    assert chunk.text == "hello"
    assert chunk.chunk_type == "abstract"
    assert chunk.chunk_index == 0
    assert chunk.metadata == {}
