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
QUESTION_GENERATION_PROMPT = """Read the following text chunk from a book on game design.
Generate {num_questions} specific questions that can ONLY be answered using information in this chunk.

Requirements:
- Questions should be specific (not vague like "What is discussed?")
- The answer must be clearly contained in the chunk text
- Mix question types: factual, conceptual, and relational
- Questions should be answerable in 1-3 sentences

Chunk ID: {chunk_id}
Chapter: {chapter_title}
Section: {section_title}

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
        chapter_title=chunk["chapter_title"],
        section_title=chunk["section_title"],
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

    # Group by chapter
    by_chapter = {}
    for c in eligible:
        ch = c["chapter_number"]
        if ch not in by_chapter:
            by_chapter[ch] = []
        by_chapter[ch].append(c)

    # Sample proportionally from each chapter
    sampled = []
    chapters = sorted(by_chapter.keys())
    per_chapter = max(1, sample_size // len(chapters))

    for ch in chapters:
        ch_chunks = by_chapter[ch]
        n = min(per_chapter, len(ch_chunks))
        sampled.extend(random.sample(ch_chunks, n))

    # If we need more, sample from remaining
    if len(sampled) < sample_size:
        remaining = [c for c in eligible if c not in sampled]
        extra = min(sample_size - len(sampled), len(remaining))
        sampled.extend(random.sample(remaining, extra))

    return sampled[:sample_size]


def save_testset(testset: List[Dict], label: str = ""):
    """Save a test set to the eval_results directory.

    Args:
        testset: List of dicts with keys:
            chunk_id, question, answer, chapter_number, section_title
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
