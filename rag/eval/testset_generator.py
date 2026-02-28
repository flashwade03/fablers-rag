"""Generate evaluation test sets from chunks.

Creates question-answer pairs where the answer is known to come from
a specific chunk. This allows measuring retrieval accuracy.

Usage in Claude Code:
    The SKILL.md instructs Claude to:
    1. Read a sample of chunks
    2. Generate questions that can be answered from each chunk
    3. Save as testset.json
"""
import json
import random
from typing import List, Dict, Optional
from pathlib import Path
from datetime import datetime

from .. import config


# Prompt template for Claude Code to generate test questions
QUESTION_GENERATION_PROMPT = """Read the following text chunk from an indexed document.
Generate {num_questions} specific questions that can ONLY be answered using information in this chunk.

Requirements:
- Questions should be specific (not vague like "What is discussed?")
- The answer must be clearly contained in the chunk text
- Mix question types: factual, conceptual, and relational
- Questions should be answerable in 1-3 sentences

Chunk ID: {chunk_id}
Heading: {heading}

Text:
{text}

Return a JSON array of objects with "question" and "answer" keys:
[
  {{"question": "...", "answer": "..."}},
  ...
]"""


def get_generation_prompt(chunk: Dict, num_questions: int = 3) -> str:
    """Generate the prompt for Claude to create test questions.

    Args:
        chunk: Chunk dict with text and metadata
        num_questions: Number of questions to generate per chunk

    Returns:
        Formatted prompt string
    """
    return QUESTION_GENERATION_PROMPT.format(
        num_questions=num_questions,
        chunk_id=chunk["chunk_id"],
        heading=chunk.get("heading", ""),
        text=chunk["text"][:2000]  # Limit text length for prompt
    )


def sample_chunks_for_eval(chunks: List[Dict],
                           sample_size: int = 30,
                           min_tokens: int = 100) -> List[Dict]:
    """Select a representative sample of chunks for evaluation.

    Ensures coverage across chapters and filters out very small chunks.

    Args:
        chunks: All chunks
        sample_size: How many chunks to sample
        min_tokens: Minimum token count to include

    Returns:
        Sampled chunks
    """
    # Filter out tiny chunks
    eligible = [c for c in chunks if c["token_estimate"] >= min_tokens]

    # Group by heading (if available), otherwise uniform sampling
    by_heading = {}
    for c in eligible:
        key = c.get("heading", "__none__")
        if key not in by_heading:
            by_heading[key] = []
        by_heading[key].append(c)

    if len(by_heading) >= 2:
        # Sample proportionally from each heading group
        sampled = []
        headings = sorted(by_heading.keys())
        per_group = max(1, sample_size // len(headings))

        for h in headings:
            group_chunks = by_heading[h]
            n = min(per_group, len(group_chunks))
            sampled.extend(random.sample(group_chunks, n))

        # If we need more, sample from remaining
        if len(sampled) < sample_size:
            remaining = [c for c in eligible if c not in sampled]
            extra = min(sample_size - len(sampled), len(remaining))
            if extra > 0:
                sampled.extend(random.sample(remaining, extra))
    else:
        # No heading groups — uniform sampling
        n = min(sample_size, len(eligible))
        sampled = random.sample(eligible, n)

    return sampled[:sample_size]


def save_testset(testset: List[Dict], label: str = ""):
    """Save a test set to the eval_results directory.

    Args:
        testset: List of dicts with keys:
            chunk_id, question, answer, heading
        label: Optional label for this testset
    """
    config.EVAL_RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"testset_{label}_{timestamp}.json" if label else f"testset_{timestamp}.json"
    path = config.EVAL_RESULTS_DIR / filename

    with open(path, "w", encoding="utf-8") as f:
        json.dump({
            "created_at": timestamp,
            "label": label,
            "num_questions": len(testset),
            "questions": testset
        }, f, indent=2, ensure_ascii=False)

    return path


def load_testset(path: Optional[Path] = None) -> List[Dict]:
    """Load the most recent testset, or a specific one.

    Returns:
        List of question dicts
    """
    if path:
        with open(path) as f:
            data = json.load(f)
        return data["questions"]

    # Find most recent testset
    config.EVAL_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    testsets = sorted(config.EVAL_RESULTS_DIR.glob("testset_*.json"))
    if not testsets:
        raise FileNotFoundError("No testset found. Generate one first.")

    with open(testsets[-1]) as f:
        data = json.load(f)
    return data["questions"]
