"""Retrieval quality evaluation metrics.

Measures how well the retrieval system finds the correct chunks
for known question-answer pairs.

Metrics:
- hit_rate@k: Fraction of questions where the source chunk is in top-k results
- MRR (Mean Reciprocal Rank): Average of 1/rank for the source chunk
"""
import json
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from pathlib import Path

from .. import config
from ..retriever import Retriever
from ..vector_store import SearchResult


def evaluate_retrieval(retriever: Retriever,
                       testset: List[Dict],
                       k_values: List[int] = None) -> Dict:
    """Run retrieval evaluation on a testset.

    Args:
        retriever: Loaded retriever instance
        testset: List of dicts with keys: chunk_id, question, answer
        k_values: List of k values to compute hit_rate@k for

    Returns:
        Dict with metrics and per-question details
    """
    k_values = k_values or [1, 3, 5, 10]
    max_k = max(k_values)

    results = []
    for item in testset:
        question = item["question"]
        expected_chunk_id = item["chunk_id"]

        # Run search
        search_results = retriever.search(question, top_k=max_k)
        retrieved_ids = [r.chunk_id for r in search_results]

        # Find rank of expected chunk (1-indexed, 0 = not found)
        rank = 0
        for i, rid in enumerate(retrieved_ids):
            if rid == expected_chunk_id:
                rank = i + 1
                break

        results.append({
            "question": question,
            "expected_chunk_id": expected_chunk_id,
            "rank": rank,
            "found": rank > 0,
            "retrieved_ids": retrieved_ids[:10],  # Store top 10 for diagnostics
            "top_result_score": search_results[0].score if search_results else 0,
            "chapter_number": item.get("chapter_number", ""),
            "section_title": item.get("section_title", "")
        })

    # Compute aggregate metrics
    total = len(results)
    metrics = {
        "total_questions": total,
    }

    # Hit rate at various k values
    for k in k_values:
        hits = sum(1 for r in results if 0 < r["rank"] <= k)
        metrics[f"hit_rate@{k}"] = round(hits / total, 4) if total > 0 else 0

    # Mean Reciprocal Rank
    reciprocal_ranks = [1.0 / r["rank"] if r["rank"] > 0 else 0 for r in results]
    metrics["mrr"] = round(sum(reciprocal_ranks) / total, 4) if total > 0 else 0

    # Failure analysis
    failures = [r for r in results if r["rank"] == 0]
    low_rank = [r for r in results if r["rank"] > 5]
    metrics["failures"] = len(failures)  # Not found in top-k at all
    metrics["low_rank_count"] = len(low_rank)  # Found but ranked > 5

    return {
        "metrics": metrics,
        "details": results,
        "k_values": k_values,
        "timestamp": datetime.now().isoformat()
    }


def save_eval_results(eval_results: Dict, label: str = "") -> Path:
    """Save evaluation results with timestamp for history tracking."""
    config.EVAL_RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"eval_{label}_{timestamp}.json" if label else f"eval_{timestamp}.json"
    path = config.EVAL_RESULTS_DIR / filename

    # Add config snapshot for reproducibility
    eval_results["config_snapshot"] = {
        "hybrid_search": config.HYBRID_SEARCH,
        "hybrid_alpha": config.HYBRID_ALPHA,
        "reranking": config.RERANKING,
        "top_k": config.TOP_K,
        "chunk_max_tokens": config.CHUNK_MAX_TOKENS,
    }

    with open(path, "w", encoding="utf-8") as f:
        json.dump(eval_results, f, indent=2, ensure_ascii=False)

    return path


def compare_evals(path_a: Path, path_b: Path) -> Dict:
    """Compare two evaluation results.

    Returns:
        Dict showing metric differences
    """
    with open(path_a) as f:
        eval_a = json.load(f)
    with open(path_b) as f:
        eval_b = json.load(f)

    metrics_a = eval_a["metrics"]
    metrics_b = eval_b["metrics"]

    comparison = {
        "eval_a": str(path_a.name),
        "eval_b": str(path_b.name),
        "config_a": eval_a.get("config_snapshot", {}),
        "config_b": eval_b.get("config_snapshot", {}),
        "metrics": {}
    }

    for key in metrics_a:
        val_a = metrics_a[key]
        val_b = metrics_b.get(key, "N/A")
        if isinstance(val_a, (int, float)) and isinstance(val_b, (int, float)):
            diff = val_b - val_a
            comparison["metrics"][key] = {
                "before": val_a,
                "after": val_b,
                "change": round(diff, 4),
                "improved": diff > 0 if key != "failures" else diff < 0
            }

    return comparison
