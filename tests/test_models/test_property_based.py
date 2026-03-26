"""Property-based tests using Hypothesis.

These tests verify invariants that must hold for all valid inputs, not just
hand-picked examples.  hypothesis generates many random inputs automatically.
"""
from __future__ import annotations

import pytest
from hypothesis import given, settings, strategies as st

from core.models.patent import SearchResult, SearchStrategy
from core.models.application import DraftApplication, Claim, FilingFormat, Specification
from core.embedding.chunker import chunk_patent_text


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _valid_specification() -> Specification:
    return Specification(
        background="Background.",
        summary="Summary.",
        detailed_description="Detailed description.",
    )


# ---------------------------------------------------------------------------
# SearchResult properties
# ---------------------------------------------------------------------------

@given(
    patent_id=st.text(min_size=1, max_size=50).filter(str.strip),
    title=st.text(min_size=1, max_size=200).filter(str.strip),
)
def test_search_result_accepts_any_valid_strings(patent_id: str, title: str):
    """SearchResult must accept any non-empty patent_id and title."""
    sr = SearchResult(
        patent_id=patent_id,
        title=title,
        provider="test",
        strategy=SearchStrategy.KEYWORD,
    )
    assert sr.patent_id == patent_id
    assert sr.title == title


@given(
    abstract=st.text(min_size=1, max_size=500),
    provider=st.sampled_from(["patentsview", "serpapi", "uspto_odp", "custom"]),
)
def test_search_result_optional_fields(abstract: str, provider: str):
    """SearchResult stores optional abstract and provider correctly."""
    sr = SearchResult(
        patent_id="US12345678",
        title="Test Patent",
        abstract=abstract,
        provider=provider,
        strategy=SearchStrategy.KEYWORD,
    )
    assert sr.abstract == abstract
    assert sr.provider == provider


# ---------------------------------------------------------------------------
# Claim properties
# ---------------------------------------------------------------------------

@given(number=st.integers(min_value=1, max_value=200))
def test_claim_number_is_always_positive_integer(number: int):
    """Claim number must be stored exactly as provided (always positive)."""
    claim = Claim(number=number, type="independent", text="A system comprising a widget.")
    assert claim.number == number
    assert claim.number > 0


@given(
    number=st.integers(min_value=1, max_value=100),
    text=st.text(min_size=1, max_size=500).filter(str.strip),
)
def test_independent_claim_has_no_depends_on(number: int, text: str):
    """Independent claims must never have a depends_on value."""
    claim = Claim(number=number, type="independent", text=text)
    assert claim.depends_on is None


# ---------------------------------------------------------------------------
# chunk_patent_text properties
# ---------------------------------------------------------------------------

@given(text=st.text(min_size=1).filter(lambda t: t.strip()))
def test_chunk_patent_text_never_produces_empty_chunks(text: str):
    """chunk_patent_text must not yield any chunk with empty text."""
    for chunk_type in ("abstract", "title", "description"):
        chunks = chunk_patent_text(text, chunk_type)
        for chunk in chunks:
            assert chunk.text.strip(), (
                f"Got empty chunk for chunk_type={chunk_type!r}"
            )


@given(
    # Generate a long text guaranteed to exceed 2048 chars (one chunk threshold)
    base=st.text(min_size=20, max_size=100).filter(str.strip),
    repeats=st.integers(min_value=50, max_value=150),
)
def test_chunk_patent_text_long_input_produces_multiple_chunks(base: str, repeats: int):
    """Very long description text (10K+ chars) must produce more than one chunk."""
    long_text = (base + "\n\n") * repeats
    # Ensure it is actually long enough
    if len(long_text) < 10_000:
        long_text = long_text * (10_000 // len(long_text) + 1)
    chunks = chunk_patent_text(long_text, "description")
    assert len(chunks) > 1, (
        f"Expected multiple chunks for {len(long_text)}-char input, got {len(chunks)}"
    )


# ---------------------------------------------------------------------------
# Abstract truncation property
# ---------------------------------------------------------------------------

@given(
    words=st.lists(
        st.text(min_size=1, max_size=15, alphabet=st.characters(whitelist_categories=("Ll", "Lu"))),
        min_size=1,
        max_size=300,
    )
)
def test_draft_application_abstract_never_exceeds_150_words(words: list[str]):
    """DraftApplication must reject abstracts exceeding 150 words."""
    abstract_text = " ".join(words)
    word_count = len(abstract_text.split())

    if word_count <= 150:
        # Must succeed
        draft = DraftApplication(
            filing_format=FilingFormat.PROVISIONAL,
            title="Test",
            abstract=abstract_text,
            specification=_valid_specification(),
        )
        assert len(draft.abstract.split()) <= 150
    else:
        # Must raise ValueError
        with pytest.raises(ValueError, match="150 words"):
            DraftApplication(
                filing_format=FilingFormat.PROVISIONAL,
                title="Test",
                abstract=abstract_text,
                specification=_valid_specification(),
            )


@given(
    chunk_type=st.sampled_from(["abstract", "title", "claim", "description"]),
    text=st.text(min_size=1).filter(lambda t: t.strip()),
)
def test_chunk_patent_text_all_chunks_have_correct_type(chunk_type: str, text: str):
    """Every chunk returned must have the chunk_type matching the requested type."""
    chunks = chunk_patent_text(text, chunk_type)
    for chunk in chunks:
        assert chunk.chunk_type == chunk_type
