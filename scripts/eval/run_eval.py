#!/usr/bin/env python3
"""Evaluate v2.0 search quality against ground-truth Q&A test set.

Runs each question through search.py and measures retrieval metrics.

Usage:
    python3 scripts/eval/run_eval.py \
        --test-set data/eval_results/testset_baseline_20260228_181429.json \
        --data-dir data \
        --api-key "$OPENAI_API_KEY" \
        --output data/eval_results/eval_v2_hybrid.json
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

# Add project root so we can import search internals directly
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))


def load_dotenv():
    """Load .env file from project root if it exists."""
    env_file = PROJECT_ROOT / ".env"
    if env_file.exists():
        with open(env_file, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, value = line.partition("=")
                    os.environ.setdefault(key.strip(), value.strip())


load_dotenv()

import numpy as np
from search import hybrid_search


def _ngram_hits(text: str, words: list, n: int) -> int:
    """Count how many n-gram phrases from words appear in text."""
    hits = 0
    for i in range(len(words) - n + 1):
        phrase = " ".join(words[i:i + n])
        if phrase in text:
            hits += 1
    return hits


def _find_best_chunk(chunk_texts: dict, words: list) -> tuple[str | None, int]:
    """Find chunk with most n-gram hits, trying 4-gram then 3-gram then 2-gram."""
    for n in (4, 3, 2):
        if len(words) < n:
            continue
        best_id = None
        best_hits = 0
        for cid, text in chunk_texts.items():
            hits = _ngram_hits(text, words, n)
            if hits > best_hits:
                best_hits = hits
                best_id = cid
        if best_hits > 0:
            return best_id, best_hits
    return None, 0


def remap_ground_truth(questions: list, chunks: list) -> tuple[list, int]:
    """Remap testset chunk_ids to current chunks via answer text matching.

    When chunks are re-generated (e.g. different chunking), IDs shift.
    Uses sliding n-gram windows from the answer (and question as fallback)
    to find the current chunk that best contains the content.

    Returns (remapped_questions, num_remapped).
    """
    chunk_texts = {c["chunk_id"]: c["text"].lower() for c in chunks}
    remapped = []
    num_remapped = 0

    for q in questions:
        old_id = q["chunk_id"]
        answer_words = q["answer"].lower().split()

        # Check if old_id still contains the answer (4-gram match)
        if old_id in chunk_texts and len(answer_words) >= 4:
            if _ngram_hits(chunk_texts[old_id], answer_words, 4) > 0:
                remapped.append(q)
                continue

        # Search all chunks using answer text
        best_id, best_hits = _find_best_chunk(chunk_texts, answer_words)

        # Fallback: try question text if answer matching fails
        if best_hits == 0:
            q_words = q["question"].lower().split()
            best_id, best_hits = _find_best_chunk(chunk_texts, q_words)

        if best_id and best_hits > 0:
            new_q = dict(q)
            new_q["chunk_id"] = best_id
            new_q["_original_chunk_id"] = old_id
            remapped.append(new_q)
            num_remapped += 1
        else:
            # Keep original (will likely be a miss)
            remapped.append(q)

    return remapped, num_remapped


def load_search_data(data_dir: Path):
    """Load chunks, embeddings, and BM25 corpus once."""
    chunks_file = data_dir / "chunks.json"
    embeddings_file = data_dir / "embeddings.npz"
    bm25_file = data_dir / "bm25_corpus.json"

    for f in [chunks_file, embeddings_file, bm25_file]:
        if not f.exists():
            print(f"Error: Missing file: {f}", file=sys.stderr)
            sys.exit(1)

    with open(chunks_file, "r", encoding="utf-8") as f:
        chunks = json.load(f)

    embeddings = np.load(embeddings_file)["embeddings"]

    with open(bm25_file, "r", encoding="utf-8") as f:
        bm25_data = json.load(f)

    return chunks, embeddings, bm25_data


def find_rank(retrieved_ids: list, expected_id: str) -> int | None:
    """Return 1-based rank of expected_id in retrieved list, or None."""
    for i, cid in enumerate(retrieved_ids):
        if cid == expected_id:
            return i + 1
    return None


def compute_metrics(details: list, top_k: int) -> dict:
    """Compute retrieval metrics from per-question details."""
    total = len(details)
    if total == 0:
        return {}

    hits_at = {k: 0 for k in [1, 3, 5, 10]}
    reciprocal_ranks = []
    failures = 0
    low_rank_count = 0  # rank > 5

    for d in details:
        rank = d["rank"]
        found = d["found"]

        if not found:
            failures += 1
            reciprocal_ranks.append(0.0)
            continue

        reciprocal_ranks.append(1.0 / rank)

        if rank > 5:
            low_rank_count += 1

        for k in hits_at:
            if rank <= k:
                hits_at[k] += 1

    metrics = {
        "total_questions": total,
        "hit_rate@1": round(hits_at[1] / total, 4),
        "hit_rate@3": round(hits_at[3] / total, 4),
        "hit_rate@5": round(hits_at[5] / total, 4),
        "hit_rate@10": round(hits_at[10] / total, 4),
        "mrr": round(sum(reciprocal_ranks) / total, 4),
        "failures": failures,
        "low_rank_count": low_rank_count,
    }
    return metrics


def run_eval(test_set_path: str, data_dir: str, api_key: str,
             top_k: int = 20, no_remap: bool = False) -> dict:
    """Run evaluation and return results dict."""
    # Load test set
    with open(test_set_path, "r", encoding="utf-8") as f:
        test_set = json.load(f)

    questions = test_set["questions"]
    print(f"Loaded {len(questions)} questions from {test_set_path}")

    # Load search data once
    data_path = Path(data_dir)
    chunks, embeddings, bm25_data = load_search_data(data_path)
    print(f"Loaded {len(chunks)} chunks, embeddings shape {embeddings.shape}")

    # Remap ground truth chunk_ids to current chunks if needed
    if not no_remap:
        questions, num_remapped = remap_ground_truth(questions, chunks)
        if num_remapped:
            print(f"Remapped {num_remapped}/{len(questions)} chunk_ids to current chunks")
    else:
        print("Skipping chunk_id remapping (--no-remap)")

    details = []
    start_time = time.time()

    for i, q in enumerate(questions):
        question = q["question"]
        expected_id = q["chunk_id"]

        # Run hybrid search directly (no subprocess overhead)
        results = hybrid_search(
            query=question,
            api_key=api_key,
            embeddings=embeddings,
            chunks=chunks,
            bm25_data=bm25_data,
            top_k=top_k,
        )

        retrieved_ids = [r["chunk_id"] for r in results]
        rank = find_rank(retrieved_ids, expected_id)

        detail = {
            "question": question,
            "expected_chunk_id": expected_id,
            "rank": rank if rank else -1,
            "found": rank is not None,
            "retrieved_ids": retrieved_ids[:10],  # top 10 for readability
        }

        if results:
            detail["top_result_score"] = results[0]["score"]

        # Carry through metadata
        for key in ("chapter_number", "section_title"):
            if key in q:
                detail[key] = q[key]

        details.append(detail)

        status = f"rank={rank}" if rank else "MISS"
        print(f"  [{i+1}/{len(questions)}] {status} | {question[:60]}...")

    elapsed = time.time() - start_time
    print(f"\nCompleted in {elapsed:.1f}s")

    metrics = compute_metrics(details, top_k)

    return {"metrics": metrics, "details": details}


def main():
    parser = argparse.ArgumentParser(
        description="Evaluate search quality against ground-truth Q&A"
    )
    parser.add_argument("--test-set", required=True,
                        help="Path to testset JSON")
    parser.add_argument("--data-dir", required=True,
                        help="Path to data directory (chunks/embeddings/bm25)")
    parser.add_argument("--api-key", default="",
                        help="OpenAI API key")
    parser.add_argument("--top-k", type=int, default=20,
                        help="Number of search results (default: 20)")
    parser.add_argument("--output", default="",
                        help="Output JSON path (default: stdout)")
    parser.add_argument("--no-remap", action="store_true",
                        help="Skip automatic chunk_id remapping (use with verified testsets)")
    args = parser.parse_args()

    api_key = args.api_key or os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        print("Error: OPENAI_API_KEY required. Use --api-key or env var.",
              file=sys.stderr)
        sys.exit(1)

    results = run_eval(args.test_set, args.data_dir, api_key, args.top_k,
                       no_remap=args.no_remap)

    # Print summary
    m = results["metrics"]
    print(f"\n{'='*50}")
    print(f"  Hit@1:  {m['hit_rate@1']:.1%}")
    print(f"  Hit@3:  {m['hit_rate@3']:.1%}")
    print(f"  Hit@5:  {m['hit_rate@5']:.1%}")
    print(f"  Hit@10: {m['hit_rate@10']:.1%}")
    print(f"  MRR:    {m['mrr']:.4f}")
    print(f"  Fails:  {m['failures']}")
    print(f"{'='*50}")

    output_json = json.dumps(results, indent=2, ensure_ascii=False)

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(output_json)
        print(f"\nResults saved to {args.output}")
    else:
        print(output_json)


if __name__ == "__main__":
    main()
