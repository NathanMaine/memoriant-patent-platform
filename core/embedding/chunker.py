from __future__ import annotations

import re

from pydantic import BaseModel

# Simple token estimator: ~4 characters per token
_CHARS_PER_TOKEN = 4
_CHUNK_TOKENS = 512
_OVERLAP_TOKENS = 64
_CHUNK_CHARS = _CHUNK_TOKENS * _CHARS_PER_TOKEN   # 2048
_OVERLAP_CHARS = _OVERLAP_TOKENS * _CHARS_PER_TOKEN  # 256

# Pattern that matches lines beginning with a claim number: "1.", "12.", etc.
_CLAIM_PATTERN = re.compile(r"(?m)^(?=\d+\.)")


class PatentChunk(BaseModel):
    text: str
    chunk_type: str
    chunk_index: int
    metadata: dict


def chunk_patent_text(text: str, chunk_type: str) -> list[PatentChunk]:
    """Split *text* into ``PatentChunk`` objects according to *chunk_type*.

    Args:
        text: The raw text to chunk.
        chunk_type: One of ``"abstract"``, ``"title"``, ``"claim"``,
            or ``"description"``.

    Returns:
        A (possibly empty) list of :class:`PatentChunk` objects.

    Raises:
        ValueError: If *chunk_type* is not recognised.
    """
    if chunk_type not in {"abstract", "title", "claim", "description"}:
        raise ValueError(f"Unknown chunk_type: {chunk_type!r}")

    if not text.strip():
        return []

    if chunk_type in {"abstract", "title"}:
        return [PatentChunk(text=text, chunk_type=chunk_type, chunk_index=0, metadata={})]

    if chunk_type == "claim":
        return _chunk_claims(text)

    # chunk_type == "description"
    return _chunk_description(text)


# ---------------------------------------------------------------------------
# Claim chunking
# ---------------------------------------------------------------------------

def _chunk_claims(text: str) -> list[PatentChunk]:
    """Split claims text at claim-number boundaries."""
    # Split on lines that start with a digit followed by a period
    parts = _CLAIM_PATTERN.split(text)
    chunks: list[PatentChunk] = []
    for raw in parts:
        stripped = raw.strip()
        if stripped:
            chunks.append(
                PatentChunk(
                    text=stripped,
                    chunk_type="claim",
                    chunk_index=len(chunks),
                    metadata={},
                )
            )
    return chunks


# ---------------------------------------------------------------------------
# Description chunking
# ---------------------------------------------------------------------------

def _chunk_description(text: str) -> list[PatentChunk]:
    """Split description text into ~512-token chunks with 64-token overlap.

    Splits are made at paragraph boundaries (double newline) where possible.
    """
    # Split into paragraphs
    paragraphs = re.split(r"\n\n+", text)

    chunks: list[PatentChunk] = []
    current_parts: list[str] = []
    current_chars = 0

    def _flush(parts: list[str]) -> None:
        chunk_text = "\n\n".join(parts).strip()
        if chunk_text:
            chunks.append(
                PatentChunk(
                    text=chunk_text,
                    chunk_type="description",
                    chunk_index=len(chunks),
                    metadata={},
                )
            )

    for para in paragraphs:
        para_chars = len(para)

        # If adding this paragraph would exceed the limit and we already have
        # content, flush and start a new chunk with overlap.
        if current_chars + para_chars > _CHUNK_CHARS and current_parts:
            _flush(current_parts)

            # Build overlap from the tail of current_parts
            overlap_parts: list[str] = []
            overlap_chars = 0
            for part in reversed(current_parts):
                if overlap_chars + len(part) <= _OVERLAP_CHARS:
                    overlap_parts.insert(0, part)
                    overlap_chars += len(part)
                else:
                    break

            current_parts = overlap_parts
            current_chars = overlap_chars

        current_parts.append(para)
        current_chars += para_chars

    # Flush any remaining content
    if current_parts:
        _flush(current_parts)

    return chunks
