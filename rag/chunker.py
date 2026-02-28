"""Universal document chunking with automatic strategy detection.

Strategy selection (in order):
1. Markdown headings — if document has >= 2 # headings
2. Structural headings — ALL-CAPS or TitleCase heuristic
3. Fallback — paragraph-based splitting
"""
import re
import json
from typing import List, Dict, Optional, Tuple
from pathlib import Path

from . import config
from .ingest import Document


def estimate_tokens(text: str) -> int:
    """Estimate token count from character count."""
    return len(text) // config.CHARS_PER_TOKEN


def chunk_document(document: Document) -> List[Dict]:
    """Main chunking pipeline: Document -> structured chunks.

    Automatically selects the best chunking strategy based on content.

    Returns:
        List of chunk dicts with keys:
            chunk_id, text, token_estimate, source_file,
            heading (optional), heading_level (optional), page_range (optional)
    """
    full_text = "\n\n".join(p.text for p in document.pages)

    # Build page map for PDF documents (character offset -> page number)
    page_map = _build_page_map(document) if document.format == "pdf" else None

    # Try strategies in order
    sections = _detect_markdown_headings(full_text)
    if sections is None:
        sections = _detect_structural_headings(document)
    if sections is None:
        sections = _fallback_paragraph_split(full_text)

    # Convert sections to chunks
    all_chunks = []
    chunk_counter = 0

    for section in sections:
        section_tokens = estimate_tokens(section["text"])

        if section_tokens <= config.CHUNK_MAX_TOKENS:
            chunk_counter += 1
            chunk = {
                "chunk_id": f"chunk_{chunk_counter:04d}",
                "text": section["text"],
                "token_estimate": section_tokens,
                "source_file": document.source_file,
            }
            if section.get("heading"):
                chunk["heading"] = section["heading"]
            if section.get("heading_level") is not None:
                chunk["heading_level"] = section["heading_level"]
            if section.get("page_range"):
                chunk["page_range"] = section["page_range"]
            all_chunks.append(chunk)
        else:
            sub_chunks = split_large_section(
                section["text"],
                config.CHUNK_MAX_TOKENS,
                config.CHUNK_OVERLAP_SENTENCES,
            )
            for i, sub_text in enumerate(sub_chunks):
                chunk_counter += 1
                heading = section.get("heading", "")
                chunk = {
                    "chunk_id": f"chunk_{chunk_counter:04d}",
                    "text": sub_text,
                    "token_estimate": estimate_tokens(sub_text),
                    "source_file": document.source_file,
                }
                if heading:
                    chunk["heading"] = f"{heading} (part {i + 1})"
                if section.get("heading_level") is not None:
                    chunk["heading_level"] = section["heading_level"]
                if section.get("page_range"):
                    chunk["page_range"] = section["page_range"]
                all_chunks.append(chunk)

    return all_chunks


# --- Strategy 1: Markdown headings ---

_MD_HEADING_RE = re.compile(r"^(#{1,4})\s+(.+)$", re.MULTILINE)


def _detect_markdown_headings(full_text: str) -> Optional[List[Dict]]:
    """Split text by Markdown headings (# through ####).

    Returns None if fewer than 2 headings found.
    """
    matches = list(_MD_HEADING_RE.finditer(full_text))
    if len(matches) < 2:
        return None

    sections = []

    # Content before first heading
    pre_text = full_text[: matches[0].start()].strip()
    if pre_text:
        sections.append({
            "text": pre_text,
            "heading": None,
            "heading_level": None,
        })

    for i, m in enumerate(matches):
        level = len(m.group(1))
        heading = m.group(2).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(full_text)
        body = full_text[start:end].strip()

        if body:
            sections.append({
                "text": body,
                "heading": heading,
                "heading_level": level,
            })

    return sections if sections else None


# --- Strategy 2: Structural headings (ALL-CAPS / TitleCase) ---

_ALLCAPS_RE = re.compile(r"^[A-Z][A-Z\s\-:,]{4,79}$")


def _is_structural_heading(line: str, prev_blank: bool) -> bool:
    """Check if a line looks like a structural heading."""
    stripped = line.strip()
    if not stripped or not prev_blank:
        return False

    # ALL-CAPS heading (5-80 chars)
    if _ALLCAPS_RE.match(stripped) and len(stripped) >= 5:
        return True

    # TitleCase heading (< 60 chars, no trailing punctuation)
    if (len(stripped) < 60
            and stripped.istitle()
            and stripped[-1] not in ".!?,;:"):
        return True

    return False


def _detect_structural_headings(document: Document) -> Optional[List[Dict]]:
    """Detect ALL-CAPS or TitleCase headings with blank-line boundaries.

    Returns None if fewer than 2 headings found.
    """
    # Combine all page text
    lines_with_pages = []
    for page in document.pages:
        page_num = page.page_number
        for line in page.text.split("\n"):
            lines_with_pages.append((line, page_num))

    # Find heading positions
    heading_indices = []
    for i, (line, _) in enumerate(lines_with_pages):
        prev_blank = (i == 0) or (not lines_with_pages[i - 1][0].strip())
        if _is_structural_heading(line, prev_blank):
            heading_indices.append(i)

    if len(heading_indices) < 2:
        return None

    sections = []

    # Content before first heading
    pre_lines = [lines_with_pages[j] for j in range(heading_indices[0])]
    pre_text = "\n".join(l for l, _ in pre_lines).strip()
    if pre_text:
        pages = [p for _, p in pre_lines if p is not None]
        sections.append({
            "text": pre_text,
            "heading": None,
            "heading_level": None,
            "page_range": [min(pages), max(pages)] if pages else None,
        })

    for idx, h_idx in enumerate(heading_indices):
        heading_text = lines_with_pages[h_idx][0].strip()
        start = h_idx + 1
        end = heading_indices[idx + 1] if idx + 1 < len(heading_indices) else len(lines_with_pages)
        body_items = lines_with_pages[start:end]
        body = "\n".join(l for l, _ in body_items).strip()

        if body:
            pages = [p for _, p in body_items if p is not None]
            sections.append({
                "text": body,
                "heading": heading_text,
                "heading_level": None,
                "page_range": [min(pages), max(pages)] if pages else None,
            })

    return sections if sections else None


# --- Strategy 3: Fallback paragraph splitting ---

def _fallback_paragraph_split(full_text: str) -> List[Dict]:
    """Split text into sections by double newlines (paragraph boundaries)."""
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", full_text) if p.strip()]

    if not paragraphs:
        return [{"text": full_text.strip(), "heading": None, "heading_level": None}]

    # Group paragraphs into sections of roughly CHUNK_MAX_TOKENS
    sections = []
    current_paras = []
    current_tokens = 0

    for para in paragraphs:
        para_tokens = estimate_tokens(para)
        if current_tokens + para_tokens > config.CHUNK_MAX_TOKENS and current_paras:
            sections.append({
                "text": "\n\n".join(current_paras),
                "heading": None,
                "heading_level": None,
            })
            current_paras = []
            current_tokens = 0
        current_paras.append(para)
        current_tokens += para_tokens

    if current_paras:
        sections.append({
            "text": "\n\n".join(current_paras),
            "heading": None,
            "heading_level": None,
        })

    return sections


# --- Shared utilities ---

def _build_page_map(document: Document) -> Dict:
    """Build a mapping for page number lookups (future use)."""
    page_map = {}
    offset = 0
    for page in document.pages:
        page_map[offset] = page.page_number
        offset += len(page.text) + 2  # +2 for "\n\n" join
    return page_map


def _split_into_paragraphs(text: str) -> List[str]:
    """Split text into paragraphs, handling various newline patterns."""
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    if len(paragraphs) > 1:
        return paragraphs

    lines = text.split("\n")
    paragraphs = []
    current = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            if current:
                paragraphs.append("\n".join(current))
                current = []
        else:
            current.append(stripped)
    if current:
        paragraphs.append("\n".join(current))

    if len(paragraphs) <= 1 and estimate_tokens(text) > config.CHUNK_MAX_TOKENS:
        sentences = re.split(r"(?<=[.!?])\s+", text.strip())
        return sentences

    return paragraphs if paragraphs else [text]


def split_large_section(section_text: str, max_tokens: int,
                        overlap_sentences: int) -> List[str]:
    """Split an oversized section into chunks by paragraph with overlap.

    Args:
        section_text: Full section text
        max_tokens: Maximum tokens per chunk
        overlap_sentences: Number of trailing sentences to repeat in next chunk

    Returns:
        List of text chunks
    """
    paragraphs = _split_into_paragraphs(section_text)

    chunks = []
    current_chunk = []
    current_tokens = 0

    for para in paragraphs:
        para_tokens = estimate_tokens(para)

        if para_tokens > max_tokens:
            sentences = re.split(r"(?<=[.!?])\s+", para)
            for sent in sentences:
                sent_tokens = estimate_tokens(sent)
                if current_tokens + sent_tokens > max_tokens and current_chunk:
                    chunks.append("\n".join(current_chunk))
                    if overlap_sentences > 0:
                        overlap = current_chunk[-overlap_sentences:]
                        current_chunk = list(overlap)
                        current_tokens = sum(estimate_tokens(s) for s in current_chunk)
                    else:
                        current_chunk = []
                        current_tokens = 0
                current_chunk.append(sent)
                current_tokens += sent_tokens
            continue

        if current_tokens + para_tokens > max_tokens and current_chunk:
            chunk_text = "\n\n".join(current_chunk)
            chunks.append(chunk_text)

            if overlap_sentences > 0:
                sentences = re.split(r"(?<=[.!?])\s+", chunk_text)
                overlap = sentences[-overlap_sentences:] if len(sentences) >= overlap_sentences else sentences
                current_chunk = [" ".join(overlap)]
                current_tokens = estimate_tokens(current_chunk[0])
            else:
                current_chunk = []
                current_tokens = 0

        current_chunk.append(para)
        current_tokens += para_tokens

    if current_chunk:
        chunks.append("\n\n".join(current_chunk))

    return chunks if chunks else [section_text]


def save_chunks(chunks: List[Dict], output_path: Optional[Path] = None):
    """Save chunks to JSON file."""
    output_path = output_path or config.CHUNKS_FILE
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(chunks, f, indent=2, ensure_ascii=False)
    return output_path


def load_chunks(input_path: Optional[Path] = None) -> List[Dict]:
    """Load chunks from JSON file."""
    input_path = input_path or config.CHUNKS_FILE
    with open(input_path, "r", encoding="utf-8") as f:
        return json.load(f)
