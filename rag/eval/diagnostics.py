"""Failure analysis and diagnostic reporting for RAG evaluation.

Analyzes why retrieval failed for specific questions and categorizes
the failure types to guide improvements.
"""
from typing import List, Dict
from collections import Counter


def diagnose_failures(eval_results: Dict, chunks: List[Dict]) -> Dict:
    """Analyze evaluation failures and produce a diagnostic report.

    Failure categories:
    - RECALL_FAILURE: Expected chunk not in top-k at all
    - RANKING_ISSUE: Expected chunk found but ranked > 5
    - SUCCESS: Expected chunk in top-5

    Args:
        eval_results: Output from evaluator.evaluate_retrieval()
        chunks: Full chunk list (for context)

    Returns:
        Diagnostic report dict
    """
    details = eval_results["details"]
    chunk_map = {c["chunk_id"]: c for c in chunks}

    recall_failures = []
    ranking_issues = []
    successes = []

    for item in details:
        if item["rank"] == 0:
            # Recall failure: chunk not found at all
            expected_chunk = chunk_map.get(item["expected_chunk_id"], {})
            recall_failures.append({
                "question": item["question"],
                "expected_chunk_id": item["expected_chunk_id"],
                "expected_heading": item.get("heading", expected_chunk.get("heading", "")),
                "expected_text_preview": expected_chunk.get("text", "")[:200],
                "retrieved_instead": item["retrieved_ids"][:5],
                "category": "RECALL_FAILURE"
            })
        elif item["rank"] > 5:
            ranking_issues.append({
                "question": item["question"],
                "expected_chunk_id": item["expected_chunk_id"],
                "actual_rank": item["rank"],
                "expected_heading": item.get("heading", ""),
                "category": "RANKING_ISSUE"
            })
        else:
            successes.append({
                "question": item["question"],
                "rank": item["rank"],
                "category": "SUCCESS"
            })

    # Heading-level failure analysis
    failure_headings = Counter()
    for f in recall_failures + ranking_issues:
        heading = f.get("expected_heading", "unknown")
        failure_headings[heading] += 1

    # Generate recommendations
    recommendations = _generate_recommendations(
        len(recall_failures), len(ranking_issues), len(successes),
        failure_headings
    )

    total = len(details)
    report = {
        "summary": {
            "total_questions": total,
            "successes": len(successes),
            "recall_failures": len(recall_failures),
            "ranking_issues": len(ranking_issues),
            "success_rate": round(len(successes) / total, 4) if total else 0
        },
        "recall_failures": recall_failures,
        "ranking_issues": ranking_issues,
        "failure_by_heading": dict(failure_headings.most_common()),
        "recommendations": recommendations
    }

    return report


def _generate_recommendations(recall_failures: int, ranking_issues: int,
                              successes: int, failure_headings: Counter) -> List[str]:
    """Generate actionable recommendations based on failure patterns."""
    total = recall_failures + ranking_issues + successes
    if total == 0:
        return ["No evaluation data available."]

    recommendations = []

    recall_rate = recall_failures / total
    ranking_rate = ranking_issues / total

    if recall_rate > 0.3:
        recommendations.append(
            f"HIGH RECALL FAILURE ({recall_rate:.0%}): Many relevant chunks are not being found. "
            "Consider enabling hybrid search (config.HYBRID_SEARCH = True) to combine "
            "keyword matching with vector search."
        )

    if recall_rate > 0.1 and recall_rate <= 0.3:
        recommendations.append(
            f"MODERATE RECALL FAILURE ({recall_rate:.0%}): Some chunks are missed. "
            "Try increasing TOP_K or adjusting chunk overlap."
        )

    if ranking_rate > 0.2:
        recommendations.append(
            f"RANKING ISSUES ({ranking_rate:.0%}): Relevant chunks are found but ranked low. "
            "Consider enabling reranking (config.RERANKING = True) for better precision."
        )

    # Heading-specific issues
    if failure_headings:
        worst_heading = failure_headings.most_common(1)[0]
        if worst_heading[1] >= 3:
            label = worst_heading[0] or "(no heading)"
            recommendations.append(
                f"Section '{label}' has the most failures ({worst_heading[1]}). "
                "Check if chunking is working correctly for this section."
            )

    if not recommendations:
        recommendations.append(
            "Retrieval quality looks good! Consider testing with more diverse questions."
        )

    return recommendations


def format_report(report: Dict) -> str:
    """Format diagnostic report as human-readable text."""
    lines = []
    s = report["summary"]

    lines.append("=" * 60)
    lines.append("RAG RETRIEVAL DIAGNOSTIC REPORT")
    lines.append("=" * 60)
    lines.append("")
    lines.append(f"Total questions: {s['total_questions']}")
    lines.append(f"Successes (top-5): {s['successes']} ({s['success_rate']:.0%})")
    lines.append(f"Recall failures:   {s['recall_failures']}")
    lines.append(f"Ranking issues:    {s['ranking_issues']}")
    lines.append("")

    if report["recommendations"]:
        lines.append("RECOMMENDATIONS:")
        for rec in report["recommendations"]:
            lines.append(f"  → {rec}")
        lines.append("")

    if report["recall_failures"]:
        lines.append(f"RECALL FAILURES ({len(report['recall_failures'])} cases):")
        for f in report["recall_failures"][:5]:  # Show top 5
            heading = f.get("expected_heading", "")[:40]
            lines.append(f"  Q: {f['question'][:80]}...")
            lines.append(f"    Expected: {f['expected_chunk_id']} ({heading})")
            lines.append(f"    Got instead: {f['retrieved_instead'][:3]}")
            lines.append("")

    if report["ranking_issues"]:
        lines.append(f"RANKING ISSUES ({len(report['ranking_issues'])} cases):")
        for r in report["ranking_issues"][:5]:
            lines.append(f"  Q: {r['question'][:80]}...")
            lines.append(f"    Expected chunk ranked #{r['actual_rank']} (should be top 5)")
            lines.append("")

    if report.get("failure_by_heading"):
        lines.append("FAILURES BY HEADING:")
        for heading, count in sorted(report["failure_by_heading"].items(), key=lambda x: str(x[0])):
            label = heading if heading else "(no heading)"
            lines.append(f"  {label}: {count} failures")

    return "\n".join(lines)
