"""BM25 keyword search for hybrid retrieval."""
import json
import re
from typing import List, Dict, Optional, Tuple
from pathlib import Path

from rank_bm25 import BM25Okapi

from .. import config


def _tokenize(text: str) -> List[str]:
    """Simple whitespace + lowercase tokenizer."""
    text = text.lower()
    text = re.sub(r'[^\w\s]', ' ', text)
    return text.split()


class BM25Index:
    """BM25 keyword search index."""

    def __init__(self):
        self.bm25: Optional[BM25Okapi] = None
        self.corpus_tokens: List[List[str]] = []
        self.chunk_ids: List[str] = []

    def build(self, chunks: List[Dict]):
        """Build BM25 index from chunks."""
        self.corpus_tokens = [_tokenize(c["text"]) for c in chunks]
        self.chunk_ids = [c["chunk_id"] for c in chunks]
        self.bm25 = BM25Okapi(self.corpus_tokens)

    def search(self, query: str, top_k: int = 20) -> List[Tuple[str, float]]:
        """Search using BM25 scoring.

        Returns:
            List of (chunk_id, bm25_score) sorted by descending score
        """
        if self.bm25 is None:
            raise ValueError("BM25 index not built. Call build() first.")

        query_tokens = _tokenize(query)
        scores = self.bm25.get_scores(query_tokens)

        top_indices = scores.argsort()[-top_k:][::-1]
        results = [(self.chunk_ids[i], float(scores[i])) for i in top_indices]
        return results

    def save(self, path: Optional[Path] = None):
        """Save corpus for rebuilding."""
        path = path or config.BM25_INDEX_FILE
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump({
                "corpus_tokens": self.corpus_tokens,
                "chunk_ids": self.chunk_ids
            }, f)

    def load(self, path: Optional[Path] = None):
        """Load and rebuild BM25 from saved corpus."""
        path = path or config.BM25_INDEX_FILE
        with open(path, "r") as f:
            data = json.load(f)
        self.corpus_tokens = data["corpus_tokens"]
        self.chunk_ids = data["chunk_ids"]
        self.bm25 = BM25Okapi(self.corpus_tokens)
