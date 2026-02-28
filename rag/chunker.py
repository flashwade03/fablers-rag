"""Structure-based chunking for textbook-style documents.

Strategy:
1. Detect chapter boundaries ("C H A P T E R" pattern)
2. Detect section boundaries (ALL-CAPS headings)
3. Split oversized sections by paragraph with overlap
4. Attach hierarchical metadata to each chunk
"""
import re
import json
from typing import List, Dict, Optional
from pathlib import Path

from . import config


def estimate_tokens(text: str) -> int:
    """Estimate token count from character count."""
    return len(text) // config.CHARS_PER_TOKEN


def detect_chapters(pages: List[Dict]) -> List[Dict]:
    """Detect chapter boundaries from pages.

    Looks for 'C H A P T E R' pattern which appears on chapter title pages.

    Returns:
        List of dicts: chapter_number, title, start_page, pages (list of page dicts)
    """
    chapters = []
    chapter_start_pages = []

    # Find all chapter start pages
    for i, page in enumerate(pages):
        if "C H A P T E R" in page["text"]:
            chapter_start_pages.append(i)

    # Also include pre-chapter content (Hello, Acknowledgments, etc.)
    # as a "Chapter 0" for completeness
    if chapter_start_pages and chapter_start_pages[0] > 0:
        pre_chapter_pages = pages[:chapter_start_pages[0]]
        # Filter out blank/TOC pages
        content_pages = [p for p in pre_chapter_pages
                        if len(p["text"]) > 100
                        and "TABLE OF CONTENTS" not in p["text"]
                        and "TABLE OF LENSES" not in p["text"]
                        and "This page intentionally" not in p["text"]]
        if content_pages:
            chapters.append({
                "chapter_number": 0,
                "title": "Introduction",
                "start_page": content_pages[0]["page_number"],
                "pages": content_pages
            })

    # Extract each chapter
    for idx, start_idx in enumerate(chapter_start_pages):
        # Chapter title page: extract chapter number and title from next page
        end_idx = chapter_start_pages[idx + 1] if idx + 1 < len(chapter_start_pages) else len(pages)
        chapter_pages = pages[start_idx:end_idx]

        # Parse chapter title from the chapter cover page itself
        # Format: "C H A P T E R\nONE\nIn the Beginning,\nThere Is the Designer"
        title = "Unknown"
        chapter_num = idx + 1
        if chapter_pages:
            cover_text = chapter_pages[0]["text"]
            cover_lines = [l.strip() for l in cover_text.split("\n") if l.strip()]
            # Find lines after "C H A P T E R" and the number word
            title_lines = []
            past_chapter_marker = False
            past_number = False
            for line in cover_lines:
                if "C H A P T E R" in line:
                    past_chapter_marker = True
                    continue
                if past_chapter_marker and not past_number:
                    # This should be the number word (ONE, TWO, etc.)
                    if line.isupper() and len(line) < 20:
                        past_number = True
                        continue
                if past_number:
                    # Skip FIGURE references
                    if line.startswith("FIGURE") or line.startswith("TABLE"):
                        break
                    # These are title lines until we hit body text (lowercase start)
                    if line[0].isupper() and not line[0].isdigit():
                        title_lines.append(line)
                    else:
                        break
            if title_lines:
                title = " ".join(title_lines)

        chapters.append({
            "chapter_number": chapter_num,
            "title": title,
            "start_page": chapter_pages[0]["page_number"],
            "pages": chapter_pages
        })

    return chapters


def detect_sections(chapter: Dict) -> List[Dict]:
    """Detect section boundaries within a chapter using ALL-CAPS headings.

    Returns:
        List of dicts: section_title, text, page_range
    """
    # Combine all page text for this chapter
    combined_lines = []
    for page in chapter["pages"]:
        for line in page["text"].split("\n"):
            combined_lines.append({
                "text": line,
                "page": page["page_number"]
            })

    # Skip the chapter title page (first page with "C H A P T E R")
    sections = []
    current_section = None
    current_lines = []
    current_pages = set()

    # Pattern for section headings: ALL CAPS, reasonable length, not a chapter header
    chapter_header_pattern = re.compile(
        r'^CHAPTER\s*(ONE|TWO|THREE|FOUR|FIVE|SIX|SEVEN|EIGHT|NINE|TEN|'
        r'ELEVEN|TWELVE|THIRTEEN|FOURTEEN|FIFTEEN|SIXTEEN|SEVENTEEN|'
        r'EIGHTEEN|NINETEEN|TWENTY|THIRTY|TWENTY-ONE|TWENTY-TWO|'
        r'TWENTY-THREE|TWENTY-FOUR|TWENTY-FIVE|TWENTY-SIX|TWENTY-SEVEN|'
        r'TWENTY-EIGHT|TWENTY-NINE|THIRTY-ONE|THIRTY-TWO)'
    )

    for item in combined_lines:
        line = item["text"].strip()
        page = item["page"]

        if not line:
            continue

        # Check if this is a section heading
        is_heading = (
            line.isupper()
            and 5 < len(line) < 80
            and "C H A P T E R" not in line
            and not chapter_header_pattern.match(line)
            and not line.startswith("FIGURE")
            and not line.startswith("TABLE")
        )

        if is_heading:
            # Save previous section
            if current_lines:
                sections.append({
                    "section_title": current_section or "Opening",
                    "text": "\n".join(current_lines),
                    "page_range": (min(current_pages), max(current_pages))
                })
            current_section = line
            current_lines = []
            current_pages = {page}
        else:
            current_lines.append(line)
            current_pages.add(page)

    # Don't forget the last section
    if current_lines:
        sections.append({
            "section_title": current_section or "Opening",
            "text": "\n".join(current_lines),
            "page_range": (min(current_pages), max(current_pages))
        })

    return sections


def _split_into_paragraphs(text: str) -> List[str]:
    """Split text into paragraphs, handling PDF text that may lack double newlines."""
    # Try double newline first
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    if len(paragraphs) > 1:
        return paragraphs

    # Fall back to single newlines, grouping consecutive lines into paragraphs
    # by detecting blank-ish transitions
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

    # If still one big block, split by sentences
    if len(paragraphs) <= 1 and estimate_tokens(text) > config.CHUNK_MAX_TOKENS:
        sentences = re.split(r'(?<=[.!?])\s+', text.strip())
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

        # If single paragraph exceeds max, split it by sentences
        if para_tokens > max_tokens:
            sentences = re.split(r'(?<=[.!?])\s+', para)
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
            # Save current chunk
            chunk_text = "\n\n".join(current_chunk)
            chunks.append(chunk_text)

            # Create overlap: take last N sentences from current chunk
            if overlap_sentences > 0:
                all_text = chunk_text
                sentences = re.split(r'(?<=[.!?])\s+', all_text)
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


def chunk_document(pages: List[Dict]) -> List[Dict]:
    """Main chunking pipeline: pages → structured chunks.

    Returns:
        List of chunk dicts with keys:
            chunk_id, text, chapter_number, chapter_title,
            section_title, page_range, token_estimate
    """
    chapters = detect_chapters(pages)
    all_chunks = []
    chunk_counter = 0

    for chapter in chapters:
        sections = detect_sections(chapter)

        for section in sections:
            section_tokens = estimate_tokens(section["text"])

            if section_tokens <= config.CHUNK_MAX_TOKENS:
                # Section fits in one chunk
                chunk_counter += 1
                all_chunks.append({
                    "chunk_id": f"chunk_{chunk_counter:04d}",
                    "text": section["text"],
                    "chapter_number": chapter["chapter_number"],
                    "chapter_title": chapter["title"],
                    "section_title": section["section_title"],
                    "page_range": list(section["page_range"]),
                    "token_estimate": section_tokens
                })
            else:
                # Split large section
                sub_chunks = split_large_section(
                    section["text"],
                    config.CHUNK_MAX_TOKENS,
                    config.CHUNK_OVERLAP_SENTENCES
                )
                for i, sub_text in enumerate(sub_chunks):
                    chunk_counter += 1
                    all_chunks.append({
                        "chunk_id": f"chunk_{chunk_counter:04d}",
                        "text": sub_text,
                        "chapter_number": chapter["chapter_number"],
                        "chapter_title": chapter["title"],
                        "section_title": f"{section['section_title']} (part {i+1})",
                        "page_range": list(section["page_range"]),
                        "token_estimate": estimate_tokens(sub_text)
                    })

    return all_chunks


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
