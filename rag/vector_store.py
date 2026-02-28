"""Numpy-based vector store with cosine similarity search."""
import json
import numpy as np
from typing import List, Dict, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass

from . import config


@dataclass
class SearchResult:
    """A single search result with flexible metadata."""
    chunk_id: str
    text: str
    score: float
    metadata: Dict  # heading, page_range, source_file, etc.

    def __repr__(self):
        heading = self.metadata.get("heading", "")
        label = heading[:30] if heading else self.chunk_id
        return f"SearchResult(chunk_id={self.chunk_id}, score={self.score:.4f}, '{label}')"


class VectorStore:
    """In-memory vector store using numpy for cosine similarity search."""

    def __init__(self):
        self.embeddings: Optional[np.ndarray] = None  # (N, dim)
        self.normalized: Optional[np.ndarray] = None   # pre-normalized for fast search
        self.metadata: List[Dict] = []
        self.chunks: List[Dict] = []  # full chunk data including text

    def build(self, embeddings: np.ndarray, chunks: List[Dict]):
        """Build the index from embeddings and chunk data.

        Args:
            embeddings: numpy array of shape (N, dim)
            chunks: list of chunk dicts (must include text)
        """
        self.embeddings = embeddings
        self.chunks = chunks
        self.metadata = [{k: v for k, v in c.items() if k != "text"} for c in chunks]

        # Pre-normalize for fast cosine similarity
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        norms = np.where(norms == 0, 1, norms)  # avoid division by zero
        self.normalized = embeddings / norms

    def search(self, query_embedding: np.ndarray, top_k: Optional[int] = None) -> List[SearchResult]:
        """Find the most similar chunks to a query embedding.

        Args:
            query_embedding: numpy array of shape (dim,)
            top_k: number of results to return

        Returns:
            List of SearchResult sorted by descending similarity
        """
        if self.normalized is None:
            raise ValueError("Vector store is empty. Call build() first.")

        top_k = top_k or config.TOP_K

        # Normalize query
        query_norm = np.linalg.norm(query_embedding)
        if query_norm == 0:
            raise ValueError("Query embedding is zero vector")
        query_normalized = query_embedding / query_norm

        # Cosine similarity via dot product (both vectors are normalized)
        similarities = np.dot(self.normalized, query_normalized)

        # Get top-k indices
        top_indices = np.argsort(similarities)[-top_k:][::-1]

        results = []
        for idx in top_indices:
            chunk = self.chunks[idx]
            metadata = {k: v for k, v in chunk.items()
                        if k not in ("chunk_id", "text")}
            results.append(SearchResult(
                chunk_id=chunk["chunk_id"],
                text=chunk["text"],
                score=float(similarities[idx]),
                metadata=metadata,
            ))

        return results

    def save(self, embeddings_path: Optional[Path] = None,
             metadata_path: Optional[Path] = None):
        """Save the vector store to disk."""
        from .embedder import save_embeddings
        save_embeddings(self.embeddings, self.chunks,
                       embeddings_path, metadata_path)

    def load(self, chunks: List[Dict],
             embeddings_path: Optional[Path] = None,
             metadata_path: Optional[Path] = None):
        """Load the vector store from disk.

        Args:
            chunks: full chunk data (with text) to pair with embeddings
        """
        from .embedder import load_embeddings
        embeddings, metadata = load_embeddings(embeddings_path, metadata_path)
        self.build(embeddings, chunks)
