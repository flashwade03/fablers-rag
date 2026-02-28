#!/usr/bin/env python3
"""Self-contained hybrid search script for the fablers-agentic-rag plugin.

Usage:
    python3 search.py --data-dir /path/to/data --queries "query1" "query2" [--top-k 20] [--per-query-min 2]

Requires: openai, numpy, rank_bm25
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path

import numpy as np
from rank_bm25 import BM25Okapi


# --- Config ---
EMBEDDING_MODEL = "text-embedding-3-small"
HYBRID_ALPHA = 0.6  # vector weight (1 - alpha = BM25 weight)
DEFAULT_TOP_K = 20


# --- Embedding ---
def embed_query(query: str, api_key: str) -> np.ndarray:
    from openai import OpenAI
    client = OpenAI(api_key=api_key)
    response = client.embeddings.create(model=EMBEDDING_MODEL, input=query)
    return np.array(response.data[0].embedding, dtype=np.float32)


# --- Vector Search ---
def vector_search(query_embedding: np.ndarray, embeddings: np.ndarray,
                  chunks: list, top_k: int) -> list:
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1, norms)
    normalized = embeddings / norms

    query_norm = np.linalg.norm(query_embedding)
    if query_norm == 0:
        return []
    query_normalized = query_embedding / query_norm

    similarities = np.dot(normalized, query_normalized)
    top_indices = np.argsort(similarities)[-top_k:][::-1]

    results = []
    for idx in top_indices:
        chunk = chunks[idx]
        results.append({
            "chunk_id": chunk["chunk_id"],
            "score": float(similarities[idx]),
        })
    return results


# --- BM25 Search ---
def bm25_search(query: str, bm25_data: dict, top_k: int) -> list:
    corpus_tokens = bm25_data["corpus_tokens"]
    chunk_ids = bm25_data["chunk_ids"]
    bm25 = BM25Okapi(corpus_tokens)

    query_tokens = re.sub(r'[^\w\s]', ' ', query.lower()).split()
    scores = bm25.get_scores(query_tokens)
    top_indices = scores.argsort()[-top_k:][::-1]

    return [(chunk_ids[i], float(scores[i])) for i in top_indices]


# --- Hybrid Search ---
def hybrid_search(query: str, api_key: str, embeddings: np.ndarray,
                  chunks: list, bm25_data: dict, top_k: int) -> list:
    query_embedding = embed_query(query, api_key)

    # Vector search
    vector_results = vector_search(query_embedding, embeddings, chunks, top_k * 2)
    vector_scores = {r["chunk_id"]: r["score"] for r in vector_results}

    # BM25 search
    bm25_results = bm25_search(query, bm25_data, top_k * 2)
    bm25_scores = dict(bm25_results)

    # Normalize BM25 scores to [0, 1]
    if bm25_scores:
        max_bm25 = max(bm25_scores.values())
        if max_bm25 > 0:
            bm25_scores = {k: v / max_bm25 for k, v in bm25_scores.items()}

    # Combine
    all_chunk_ids = set(vector_scores.keys()) | set(bm25_scores.keys())
    combined = {}
    for cid in all_chunk_ids:
        vs = vector_scores.get(cid, 0)
        bs = bm25_scores.get(cid, 0)
        combined[cid] = HYBRID_ALPHA * vs + (1 - HYBRID_ALPHA) * bs

    sorted_ids = sorted(combined.keys(), key=lambda x: combined[x], reverse=True)

    chunk_map = {c["chunk_id"]: c for c in chunks}
    results = []
    for cid in sorted_ids[:top_k]:
        chunk = chunk_map.get(cid)
        if chunk:
            results.append({
                "chunk_id": cid,
                "text": chunk["text"],
                "score": round(combined[cid], 4),
                "chapter_number": chunk["chapter_number"],
                "chapter_title": chunk["chapter_title"],
                "section_title": chunk["section_title"],
                "page_range": chunk["page_range"],
                "matched_query": query,
            })
    return results


def main():
    parser = argparse.ArgumentParser(description="Hybrid search over RAG index")
    parser.add_argument("--data-dir", required=True, help="Path to data directory")
    parser.add_argument("--queries", nargs="+", required=True, help="Search queries")
    parser.add_argument("--top-k", type=int, default=DEFAULT_TOP_K)
    parser.add_argument("--per-query-min", type=int, default=2,
                        help="Minimum unique results guaranteed per query")
    parser.add_argument("--api-key", default="", help="OpenAI API key")
    args = parser.parse_args()

    data_dir = Path(args.data_dir)

    # Validate data directory
    chunks_file = data_dir / "chunks.json"
    embeddings_file = data_dir / "embeddings.npz"
    bm25_file = data_dir / "bm25_corpus.json"

    for f in [chunks_file, embeddings_file, bm25_file]:
        if not f.exists():
            print(json.dumps({"error": f"Missing file: {f}"}))
            sys.exit(1)

    # API key: argument > env var
    api_key = args.api_key or os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        print(json.dumps({"error": "OPENAI_API_KEY not set. Pass --api-key or set the environment variable."}))
        sys.exit(1)

    # Load data
    with open(chunks_file, "r", encoding="utf-8") as f:
        chunks = json.load(f)

    embeddings = np.load(embeddings_file)["embeddings"]

    with open(bm25_file, "r", encoding="utf-8") as f:
        bm25_data = json.load(f)

    # Run searches per query
    per_query_results = {}
    for query in args.queries:
        per_query_results[query] = hybrid_search(
            query, api_key, embeddings, chunks, bm25_data, args.top_k
        )

    # Phase 1: Guarantee per_query_min unique results per query (score-ordered)
    per_query_min = args.per_query_min
    seen_chunk_ids = set()
    guaranteed = []

    for query, results in per_query_results.items():
        count = 0
        for r in results:
            if r["chunk_id"] not in seen_chunk_ids and count < per_query_min:
                seen_chunk_ids.add(r["chunk_id"])
                guaranteed.append(r)
                count += 1

    # Phase 2: Fill remaining slots from all results by score
    remaining = []
    for results in per_query_results.values():
        for r in results:
            if r["chunk_id"] not in seen_chunk_ids:
                seen_chunk_ids.add(r["chunk_id"])
                remaining.append(r)
    remaining.sort(key=lambda x: x["score"], reverse=True)

    merged_results = guaranteed + remaining
    merged_results = merged_results[:args.top_k]

    print("RETRIEVAL_RESULTS:")
    print(json.dumps(merged_results, indent=2, ensure_ascii=False))
    print(f"\nTotal unique chunks retrieved: {len(merged_results)}")


if __name__ == "__main__":
    main()
