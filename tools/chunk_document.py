"""
Tool: Chunk Document
Splits extracted text into overlapping chunks for the RAG pipeline.
Deterministic — no LLM involvement.
"""

import uuid
import os
import sys
from datetime import datetime, timezone
from typing import List

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from loguru import logger
from src.config import settings


def chunk_text(
    text: str,
    source_file: str,
    source_type: str,
    user_id: str,
    chunk_size: int = None,
    chunk_overlap: int = None,
) -> List[dict]:
    """
    Split text into overlapping chunks with metadata.

    Uses recursive character splitting with configurable size and overlap.

    Args:
        text: Raw text to chunk
        source_file: Original filename
        source_type: Evidence type (screenshot, pdf, jira_ticket, document, text)
        user_id: Requesting user's ID
        chunk_size: Token window size (default from settings: 500)
        chunk_overlap: Overlap between chunks (default from settings: 100)

    Returns:
        List of chunk dicts with content and metadata
    """
    if not text or not text.strip():
        logger.warning("Empty text provided for chunking")
        return []

    chunk_size = chunk_size or settings.chunk_size
    chunk_overlap = chunk_overlap or settings.chunk_overlap

    logger.info(
        f"Chunking text: {len(text)} chars, "
        f"size={chunk_size}, overlap={chunk_overlap}"
    )

    # Separators in priority order
    separators = ["\n\n", "\n", ". ", " "]
    chunks = _recursive_split(text, separators, chunk_size, chunk_overlap)

    # Build chunk objects with metadata
    timestamp = datetime.now(timezone.utc).isoformat()
    result = []

    for idx, chunk_text_content in enumerate(chunks):
        chunk_obj = {
            "content": chunk_text_content,
            "metadata": {
                "chunk_id": str(uuid.uuid4()),
                "source_file": source_file,
                "source_type": source_type,
                "user_id": user_id,
                "timestamp": timestamp,
                "chunk_index": idx,
                "char_count": len(chunk_text_content),
            },
        }
        result.append(chunk_obj)

    logger.info(f"Created {len(result)} chunks from text")
    return result


def _recursive_split(
    text: str,
    separators: list,
    chunk_size: int,
    chunk_overlap: int,
) -> List[str]:
    """
    Recursively split text using separators, ensuring chunks
    don't exceed chunk_size (approximate by character count).

    We approximate tokens as ~4 chars per token.
    """
    char_limit = chunk_size * 4  # ~4 chars per token
    char_overlap = chunk_overlap * 4

    if len(text) <= char_limit:
        return [text.strip()] if text.strip() else []

    # Find the best separator
    separator = " "
    for sep in separators:
        if sep in text:
            separator = sep
            break

    # Split by separator
    parts = text.split(separator)

    chunks = []
    current_chunk = ""

    for part in parts:
        candidate = (
            current_chunk + separator + part if current_chunk else part
        )

        if len(candidate) <= char_limit:
            current_chunk = candidate
        else:
            if current_chunk.strip():
                chunks.append(current_chunk.strip())

            # Apply overlap: keep the tail of the current chunk
            if char_overlap > 0 and current_chunk:
                overlap_text = current_chunk[-char_overlap:]
                current_chunk = overlap_text + separator + part
            else:
                current_chunk = part

            # If a single part exceeds the limit, force-split it
            if len(current_chunk) > char_limit:
                while len(current_chunk) > char_limit:
                    chunks.append(current_chunk[:char_limit].strip())
                    current_chunk = current_chunk[char_limit - char_overlap:]

    # Don't forget the last chunk
    if current_chunk.strip():
        chunks.append(current_chunk.strip())

    return chunks


def chunk_document_from_file(
    file_path: str,
    source_type: str,
    user_id: str,
) -> List[dict]:
    """
    Read a text file and chunk it.
    Convenience wrapper for the RAG pipeline.
    """
    if not os.path.exists(file_path):
        logger.error(f"File not found: {file_path}")
        return []

    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        text = f.read()

    return chunk_text(
        text=text,
        source_file=os.path.basename(file_path),
        source_type=source_type,
        user_id=user_id,
    )
