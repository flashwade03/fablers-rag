"""Unified retrieval engine with optional hybrid search and reranking."""
import numpy as np
from typing import List, Optional

from . import config
from .vector_store import VectorStore, SearchResult
from .embedder import embed_query
from .chunker import load_chunks


class Retriever:
    """Main retrieval interface combining vector search with optional improvements."""

    def __init__(self, vector_store: Optional[VectorStore] = None):
        self.vector_store = vector_store or VectorStore()
        self.bm25_index = None
        self._chunks = None

    def load(self):
        """Load all indexes from disk."""
        self._chunks = load_chunks()
        self.vector_store.load(self._chunks)

        if config.HYBRID_SEARCH:
            self._load_bm25()

    def _load_bm25(self):
        """Load or build BM25 index."""
        from .improvements.hybrid_search import BM25Index
        self.bm25_index = BM25Index()

        if config.BM25_INDEX_FILE.exists():
            self.bm25_index.load()
        else:
            # Build from chunks
            self.bm25_index.build(self._chunks)
            self.bm25_index.save()

    def search(self, query: str, top_k: Optional[int] = None) -> List[SearchResult]:
        """Search for relevant chunks.

        Uses vector search by default. When config.HYBRID_SEARCH is True,
        combines vector + BM25 scores. When config.RERANKING is True,
        fetches more results and returns a rerank prompt.

        Args:
            query: Search query string
            top_k: Number of results (defaults to config.TOP_K)

        Returns:
            List of SearchResult sorted by relevance
        """
        top_k = top_k or config.TOP_K

        # Determine how many to fetch initially
        fetch_k = config.RERANK_INITIAL_K if config.RERANKING else top_k

        if config.HYBRID_SEARCH and self.bm25_index:
            results = self._hybrid_search(query, fetch_k)
        else:
            results = self._vector_search(query, fetch_k)

        if config.RERANKING:
            # Return more results for Claude to rerank
            return results[:fetch_k]

        return results[:top_k]

    def _vector_search(self, query: str, top_k: int) -> List[SearchResult]:
        """Pure vector similarity search."""
        query_embedding = embed_query(query)
        return self.vector_store.search(query_embedding, top_k=top_k)

    def _hybrid_search(self, query: str, top_k: int) -> List[SearchResult]:
        """Combine vector search and BM25 keyword search.

        Scores are combined using: alpha * vector_score + (1-alpha) * normalized_bm25_score
        """
        alpha = config.HYBRID_ALPHA

        # Vector search (get more for better fusion)
        query_embedding = embed_query(query)
        vector_results = self.vector_store.search(query_embedding, top_k=top_k * 2)

        # BM25 search
        bm25_results = self.bm25_index.search(query, top_k=top_k * 2)

        # Build score maps
        vector_scores = {r.chunk_id: r.score for r in vector_results}
        bm25_scores = dict(bm25_results)

        # Normalize BM25 scores to [0, 1]
        if bm25_scores:
            max_bm25 = max(bm25_scores.values())
            if max_bm25 > 0:
                bm25_scores = {k: v / max_bm25 for k, v in bm25_scores.items()}

        # Combine scores for all candidate chunks
        all_chunk_ids = set(vector_scores.keys()) | set(bm25_scores.keys())
        combined = {}
        for cid in all_chunk_ids:
            vs = vector_scores.get(cid, 0)
            bs = bm25_scores.get(cid, 0)
            combined[cid] = alpha * vs + (1 - alpha) * bs

        # Sort by combined score and build results
        sorted_ids = sorted(combined.keys(), key=lambda x: combined[x], reverse=True)

        # Build SearchResult objects
        chunk_map = {c["chunk_id"]: c for c in self._chunks}
        results = []
        for cid in sorted_ids[:top_k]:
            chunk = chunk_map.get(cid)
            if chunk:
                results.append(SearchResult(
                    chunk_id=cid,
                    text=chunk["text"],
                    score=combined[cid],
                    chapter_number=chunk["chapter_number"],
                    chapter_title=chunk["chapter_title"],
                    section_title=chunk["section_title"],
                    page_range=chunk["page_range"]
                ))

        return results

    def get_context_for_query(self, query: str, top_k: Optional[int] = None) -> str:
        """Search and format results as context for LLM consumption.

        Returns a formatted string with search results that can be
        directly inserted into a prompt.
        """
        results = self.search(query, top_k)

        parts = []
        for i, r in enumerate(results):
            parts.append(
                f"[Source {i+1}] Chapter {r.chapter_number}: {r.chapter_title} "
                f"> {r.section_title} (pages {r.page_range[0]}-{r.page_range[1]})\n"
                f"{r.text}"
            )

        return "\n\n---\n\n".join(parts)
