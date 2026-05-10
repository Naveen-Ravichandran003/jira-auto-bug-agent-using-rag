"""
Tool: Retrieve Context
Retrieves relevant document chunks from the vector store for bug generation.
Applies similarity threshold and multi-tenant filtering.
"""

import os
import sys
from typing import List, Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from loguru import logger
from src.config import settings
from tools.embed_chunks import get_store


def retrieve_context(
    query: str,
    user_id: str,
    top_k: int = None,
    similarity_threshold: float = None,
) -> dict:
    """
    Retrieve relevant context chunks for bug generation.

    Enforces:
    - Top-K retrieval (default: 5)
    - Similarity threshold filtering (default: 0.7)
    - User isolation (multi-tenant)

    Args:
        query: The search query (user's bug description or evidence text)
        user_id: User ID for multi-tenant filtering
        top_k: Number of results to retrieve
        similarity_threshold: Minimum similarity score

    Returns:
        dict with:
            - success: bool
            - chunks: list of relevant chunks
            - avg_similarity: float
            - chunk_count: int
    """
    top_k = top_k or settings.top_k
    similarity_threshold = similarity_threshold or settings.similarity_threshold

    logger.info(
        f"Retrieving context: top_k={top_k}, "
        f"threshold={similarity_threshold}, user={user_id}"
    )

    try:
        store = get_store()

        # Search the vector store
        raw_results = store.search(
            query=query,
            top_k=top_k * 2,  # Fetch extra to allow threshold filtering
            user_id=user_id,
        )

        if not raw_results:
            logger.warning("No results returned from vector store")
            return {
                "success": False,
                "chunks": [],
                "avg_similarity": 0.0,
                "chunk_count": 0,
                "error": "No matching evidence found in the knowledge base",
            }

        # Filter by similarity threshold
        filtered_chunks = [
            r for r in raw_results
            if r["similarity_score"] >= similarity_threshold
        ]

        # Limit to top_k
        filtered_chunks = filtered_chunks[:top_k]

        if not filtered_chunks:
            logger.warning(
                f"All {len(raw_results)} results below threshold "
                f"({similarity_threshold}). Best score: "
                f"{raw_results[0]['similarity_score']:.4f}"
            )
            return {
                "success": False,
                "chunks": [],
                "avg_similarity": 0.0,
                "chunk_count": 0,
                "best_score": raw_results[0]["similarity_score"] if raw_results else 0,
                "error": (
                    f"No evidence chunks met the similarity threshold "
                    f"({similarity_threshold}). Best match: "
                    f"{raw_results[0]['similarity_score']:.2f}"
                ),
            }

        # Calculate average similarity
        avg_similarity = sum(
            c["similarity_score"] for c in filtered_chunks
        ) / len(filtered_chunks)

        # Extract chunk_ids for evidence tracing
        chunk_ids = [
            c["metadata"].get("chunk_id", "unknown")
            for c in filtered_chunks
        ]

        logger.info(
            f"Retrieved {len(filtered_chunks)} chunks, "
            f"avg similarity: {avg_similarity:.4f}"
        )

        return {
            "success": True,
            "chunks": filtered_chunks,
            "chunk_ids": chunk_ids,
            "avg_similarity": round(avg_similarity, 4),
            "chunk_count": len(filtered_chunks),
        }

    except Exception as e:
        logger.error(f"Context retrieval failed: {str(e)}")
        return {
            "success": False,
            "chunks": [],
            "avg_similarity": 0.0,
            "chunk_count": 0,
            "error": str(e),
        }


def format_context_for_llm(chunks: List[dict]) -> str:
    """
    Format retrieved chunks into a context string for the LLM prompt.

    Each chunk is labeled with its chunk_id for evidence tracing.
    """
    if not chunks:
        return ""

    context_parts = []
    for i, chunk in enumerate(chunks, 1):
        chunk_id = chunk.get("metadata", {}).get("chunk_id", f"chunk_{i}")
        source = chunk.get("metadata", {}).get("source_file", "unknown")
        score = chunk.get("similarity_score", 0.0)
        content = chunk.get("content", "")

        context_parts.append(
            f"[CHUNK {i} | ID: {chunk_id} | Source: {source} | "
            f"Similarity: {score:.3f}]\n{content}\n"
        )

    return "\n---\n".join(context_parts)
