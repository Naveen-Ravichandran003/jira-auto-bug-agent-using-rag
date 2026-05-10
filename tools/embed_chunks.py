"""
Tool: Embed Chunks
Generates embeddings for text chunks and manages FAISS vector store.
Deterministic embedding — no generative LLM involvement.
"""

import os
import sys
import json
import pickle
from typing import List, Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from loguru import logger
from src.config import settings

try:
    import numpy as np
    import faiss
    # Removed OpenAI import
    EMBED_AVAILABLE = True
except ImportError:
    EMBED_AVAILABLE = False
    logger.warning("Core embedding dependencies not installed (faiss-cpu, numpy)")

try:
    from sentence_transformers import SentenceTransformer
    LOCAL_EMBED_AVAILABLE = True
except ImportError:
    LOCAL_EMBED_AVAILABLE = False


class EmbeddingStore:
    """
    Manages FAISS vector store for document chunk embeddings.
    Supports per-session indexing with user isolation.
    """

    def __init__(self, index_path: str = None):
        self.index_path = index_path or settings.faiss_index_path
        self.index: Optional["faiss.IndexFlatL2"] = None
        self.metadata_store: List[dict] = []
        self.local_model: Optional["SentenceTransformer"] = None
        
        # Local dimension
        self.dimension = 384 

        if EMBED_AVAILABLE:
            if LOCAL_EMBED_AVAILABLE:
                logger.info(f"Loading local embedding model: {settings.embedding_model}...")
                self.local_model = SentenceTransformer(settings.embedding_model)
                self.dimension = self.local_model.get_sentence_embedding_dimension()

    def _ensure_index(self):
        """Create or load FAISS index."""
        if self.index is not None:
            return

        index_file = os.path.join(self.index_path, "index.faiss")
        meta_file = os.path.join(self.index_path, "metadata.pkl")

        if os.path.exists(index_file) and os.path.exists(meta_file):
            self.index = faiss.read_index(index_file)
            with open(meta_file, "rb") as f:
                self.metadata_store = pickle.load(f)
            logger.info(
                f"Loaded FAISS index: {self.index.ntotal} vectors, "
                f"{len(self.metadata_store)} metadata entries"
            )
        else:
            self.index = faiss.IndexFlatL2(self.dimension)
            self.metadata_store = []
            logger.info("Created new FAISS index")

    def _save_index(self):
        """Persist FAISS index and metadata to disk."""
        os.makedirs(self.index_path, exist_ok=True)

        index_file = os.path.join(self.index_path, "index.faiss")
        meta_file = os.path.join(self.index_path, "metadata.pkl")

        faiss.write_index(self.index, index_file)
        with open(meta_file, "wb") as f:
            pickle.dump(self.metadata_store, f)

        logger.debug(f"Saved FAISS index to {self.index_path}")

    def generate_embeddings(self, texts: List[str], api_key_override: str = None) -> "np.ndarray":
        """
        Generate embeddings for a list of texts using Local Sentence Transformers.
        """
        if not LOCAL_EMBED_AVAILABLE:
            raise RuntimeError("Local embedding dependencies (sentence-transformers) not installed")
        
        if not self.local_model:
            logger.info(f"Lazy loading local model: {settings.embedding_model}")
            self.local_model = SentenceTransformer(settings.embedding_model)
            self.dimension = self.local_model.get_sentence_embedding_dimension()
        
        logger.info(f"Generating Local embeddings ({settings.embedding_model}) for {len(texts)} texts")
        embeddings = self.local_model.encode(texts)
        return np.array(embeddings, dtype=np.float32)

    def add_chunks(self, chunks: List[dict], persist: bool = True, api_key_override: str = None) -> int:
        """
        Embed and add chunks to the FAISS index.

        Args:
            chunks: List of chunk dicts from chunk_document tool
            persist: Whether to save to disk after adding
            api_key_override: Optional per-user API key

        Returns:
            Number of chunks added
        """
        if not EMBED_AVAILABLE:
            raise RuntimeError(
                "Embedding dependencies not available. "
                "Install: pip install faiss-cpu openai numpy"
            )

        self._ensure_index()

        if not chunks:
            logger.warning("No chunks to add")
            return 0

        # Extract texts and metadata
        texts = [c["content"] for c in chunks]
        metadata_list = [c["metadata"] for c in chunks]

        # Generate embeddings
        embeddings = self.generate_embeddings(texts, api_key_override=api_key_override)

        # Add to FAISS index
        self.index.add(embeddings)
        self.metadata_store.extend(metadata_list)

        if persist:
            self._save_index()

        logger.info(
            f"Added {len(chunks)} chunks to index. "
            f"Total vectors: {self.index.ntotal}"
        )
        return len(chunks)

    def search(
        self,
        query: str,
        top_k: int = None,
        user_id: str = None,
        api_key_override: str = None,
    ) -> List[dict]:
        """
        Search for similar chunks in the FAISS index.

        Args:
            query: Search query text
            top_k: Number of results to return
            user_id: Optional filter by user_id

        Returns:
            List of dicts with content, metadata, and similarity_score
        """
        if not EMBED_AVAILABLE:
            raise RuntimeError("Embedding dependencies not available")

        self._ensure_index()
        top_k = top_k or settings.top_k

        if self.index.ntotal == 0:
            logger.warning("FAISS index is empty — no chunks to search")
            return []

        # Embed the query
        query_embedding = self.generate_embeddings([query], api_key_override=api_key_override)

        # Search (retrieve more than top_k to allow for user_id filtering)
        search_k = min(top_k * 3, self.index.ntotal)
        distances, indices = self.index.search(query_embedding, search_k)

        results = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx < 0 or idx >= len(self.metadata_store):
                continue

            metadata = self.metadata_store[idx]

            # Filter by user_id if specified (multi-tenant isolation)
            if user_id and metadata.get("user_id") != user_id:
                continue

            # Convert L2 distance to similarity score (0-1 range)
            # Lower L2 distance = higher similarity
            similarity = 1.0 / (1.0 + float(dist))

            results.append({
                "content": self._get_chunk_content(idx),
                "metadata": metadata,
                "similarity_score": round(similarity, 4),
                "l2_distance": float(dist),
            })

            if len(results) >= top_k:
                break

        logger.info(
            f"Search returned {len(results)} results "
            f"(query: '{query[:50]}...')"
        )
        return results

    def _get_chunk_content(self, idx: int) -> str:
        """Retrieve original chunk content by index."""
        # Since FAISS only stores vectors, we need to reconstruct content
        # from metadata. In production, use a separate content store.
        # For now, content is stored alongside metadata during add_chunks.
        # We'll enhance this in the full pipeline.
        return self.metadata_store[idx].get("_content", "[Content not stored]")

    def add_chunks_with_content(self, chunks: List[dict], persist: bool = True, api_key_override: str = None) -> int:
        """
        Add chunks and store content alongside metadata for retrieval.
        """
        if not EMBED_AVAILABLE:
            raise RuntimeError("Embedding dependencies not available")

        self._ensure_index()

        if not chunks:
            return 0

        texts = [c["content"] for c in chunks]

        # Store content in metadata for retrieval
        metadata_with_content = []
        for c in chunks:
            meta = dict(c["metadata"])
            meta["_content"] = c["content"]
            metadata_with_content.append(meta)

        embeddings = self.generate_embeddings(texts, api_key_override=api_key_override)
        self.index.add(embeddings)
        self.metadata_store.extend(metadata_with_content)

        if persist:
            self._save_index()

        logger.info(f"Added {len(chunks)} chunks with content to index")
        return len(chunks)

    def clear_user_data(self, user_id: str):
        """
        Clear all data for a specific user (session cleanup).
        Note: FAISS doesn't support selective deletion efficiently.
        For production, rebuild the index excluding the user's chunks.
        """
        logger.info(f"Clearing data for user: {user_id}")
        # Filter metadata
        remaining = [
            m for m in self.metadata_store
            if m.get("user_id") != user_id
        ]
        removed_count = len(self.metadata_store) - len(remaining)
        self.metadata_store = remaining

        # Rebuild index if items were removed
        if removed_count > 0:
            logger.info(f"Removed {removed_count} chunks for user {user_id}")
            # Note: Full index rebuild would be needed for FAISS
            # This is a simplified version for the MVP

    def reset(self):
        """Reset the entire index. Use with caution."""
        self.index = faiss.IndexFlatL2(self.dimension)
        self.metadata_store = []
        self._save_index()
        logger.info("FAISS index reset")


# Module-level singleton
_store = None


def get_store() -> EmbeddingStore:
    """Get or create the singleton EmbeddingStore instance."""
    global _store
    if _store is None:
        _store = EmbeddingStore()
    return _store
