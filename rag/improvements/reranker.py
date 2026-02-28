"""Claude-based reranking for search results."""
from typing import List
from ..vector_store import SearchResult


RERANK_PROMPT = """You are a search result reranker. Given a query and a list of text passages,
rank them by relevance to the query. Return ONLY a comma-separated list of the passage numbers
in order from most relevant to least relevant.

Query: {query}

Passages:
{passages}

Return ONLY the numbers in order (e.g., "3,1,5,2,4"). No explanation needed."""


def rerank(query: str, results: List[SearchResult],
           final_k: int = 10) -> List[SearchResult]:
    """Rerank search results using Claude.

    This function is designed to be called by Claude Code itself.
    In the SKILL.md, Claude will:
    1. Get initial search results (top 20)
    2. Format them into the rerank prompt
    3. Use its own judgment to reorder
    4. Return the top-k

    Since we're running inside Claude Code, the "reranking"
    is actually done by Claude reading the results and picking
    the most relevant ones. This module provides the prompt template.

    Args:
        query: The search query
        results: Initial search results to rerank
        final_k: Number of results to keep after reranking

    Returns:
        Reranked list of SearchResult (top final_k)
    """
    # Build the prompt for Claude to rerank
    passages = []
    for i, r in enumerate(results):
        heading = r.metadata.get("heading", "")
        passages.append(f"[{i+1}] ({heading})\n{r.text[:500]}")

    prompt = RERANK_PROMPT.format(
        query=query,
        passages="\n\n".join(passages)
    )

    # In practice, this prompt is used by Claude Code to do the reranking
    # The SKILL.md will instruct Claude to evaluate and reorder
    return results[:final_k], prompt


def get_rerank_prompt(query: str, results: List[SearchResult]) -> str:
    """Generate the reranking prompt for Claude to evaluate.

    Returns the formatted prompt string that Claude Code will process.
    """
    passages = []
    for i, r in enumerate(results):
        heading = r.metadata.get("heading", "")
        passages.append(f"[{i+1}] ({heading})\n{r.text[:500]}")

    return RERANK_PROMPT.format(
        query=query,
        passages="\n\n".join(passages)
    )
