#!/usr/bin/env python3
"""Multi-format document extraction and ingestion pipeline.

Supported formats: PDF, plain text, Markdown.

Usage:
    python3 ingest.py --document ./mybook.pdf --output-dir ./data
    python3 ingest.py --document ./notes.md --output-dir ./data/notes --skip-embeddings
"""
import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import pdfplumber


@dataclass
class DocumentPage:
    """A single page (or logical section) of extracted text."""
    text: str
    page_number: Optional[int] = None  # PDF only


@dataclass
class Document:
    """Extracted document with pages and metadata."""
    pages: List[DocumentPage]
    source_file: str
    format: str  # "pdf" | "txt" | "md"


def extract(file_path: str) -> Document:
    """Detect format by extension and extract text.

    Args:
        file_path: Path to a PDF, TXT, or Markdown file.

    Returns:
        Document with extracted pages.

    Raises:
        FileNotFoundError: If file does not exist.
        ValueError: If format is unsupported.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return _extract_pdf(path)
    elif suffix == ".txt":
        return _extract_text(path)
    elif suffix in (".md", ".markdown"):
        return _extract_markdown(path)
    else:
        raise ValueError(
            f"Unsupported file format: '{suffix}'. "
            "Supported: .pdf, .txt, .md, .markdown"
        )


def _extract_pdf(path: Path) -> Document:
    """Extract text from each page of a PDF using pdfplumber."""
    pages = []
    with pdfplumber.open(path) as pdf:
        for i, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            if text.strip():
                pages.append(DocumentPage(
                    text=text.strip(),
                    page_number=i + 1,
                ))

    return Document(pages=pages, source_file=str(path), format="pdf")


def _extract_text(path: Path) -> Document:
    """Load a plain text file as a single page."""
    text = path.read_text(encoding="utf-8")
    pages = [DocumentPage(text=text.strip())] if text.strip() else []
    return Document(pages=pages, source_file=str(path), format="txt")


def _extract_markdown(path: Path) -> Document:
    """Load a Markdown file as a single page, preserving heading markers."""
    text = path.read_text(encoding="utf-8")
    pages = [DocumentPage(text=text.strip())] if text.strip() else []
    return Document(pages=pages, source_file=str(path), format="md")


def _read_settings_api_key(settings_path: Optional[str] = None) -> str:
    """Read openai_api_key from .claude/fablers-agentic-rag.local.md YAML frontmatter.

    Search order:
    1. Explicit --settings path
    2. $CLAUDE_PROJECT_DIR/.claude/fablers-agentic-rag.local.md
    3. ./.claude/fablers-agentic-rag.local.md
    """
    candidates = []
    if settings_path:
        candidates.append(Path(settings_path))
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", "")
    if project_dir:
        candidates.append(Path(project_dir) / ".claude" / "fablers-agentic-rag.local.md")
    candidates.append(Path.cwd() / ".claude" / "fablers-agentic-rag.local.md")

    for path in candidates:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        # Parse YAML frontmatter between --- markers
        if text.startswith("---"):
            parts = text.split("---", 2)
            if len(parts) >= 3:
                for line in parts[1].strip().splitlines():
                    line = line.strip()
                    if line.startswith("openai_api_key:"):
                        key = line.split(":", 1)[1].strip()
                        if key and key != "YOUR_OPENAI_API_KEY":
                            return key
    return ""


def main():
    parser = argparse.ArgumentParser(
        description="Ingest a document into the RAG pipeline "
                    "(extract -> chunk -> embed -> BM25 index)."
    )
    parser.add_argument(
        "--document", required=True,
        help="Path to the source document (PDF, TXT, or Markdown)."
    )
    parser.add_argument(
        "--output-dir", required=True,
        help="Directory where chunks, embeddings, and indexes are saved."
    )
    parser.add_argument(
        "--skip-embeddings", action="store_true",
        help="Stop after chunking (skip embedding and BM25 index generation)."
    )
    parser.add_argument(
        "--api-key", default="",
        help="OpenAI API key. Falls back to settings file or OPENAI_API_KEY env var."
    )
    parser.add_argument(
        "--settings", default="",
        help="Path to fablers-agentic-rag.local.md settings file."
    )
    args = parser.parse_args()

    doc_path = Path(args.document)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Resolve API key: --api-key > settings file > env var
    api_key = (args.api_key
               or _read_settings_api_key(args.settings or None)
               or os.environ.get("OPENAI_API_KEY", ""))

    # --- Step 1: Extract ---
    print(f"[1/4] Extracting text from {doc_path.name} ...")
    document = extract(str(doc_path))
    print(f"       Extracted {len(document.pages)} page(s), format={document.format}")

    # --- Step 2: Chunk ---
    print(f"[2/4] Chunking document ...")
    from chunker import chunk_document, save_chunks
    chunks = chunk_document(document)
    chunks_file = output_dir / "chunks.json"
    save_chunks(chunks, chunks_file)
    print(f"       Created {len(chunks)} chunks -> {chunks_file}")

    if args.skip_embeddings:
        print("[3/4] Skipped (--skip-embeddings)")
        print("[4/4] Skipped (--skip-embeddings)")
        print("\nDone! Chunks saved. Use without --skip-embeddings to generate embeddings.")
        return

    # Require API key for embedding step
    if not api_key:
        print("Error: OpenAI API key required for embeddings.")
        print("Provide via --api-key, configure in .claude/fablers-agentic-rag.local.md,")
        print("or set OPENAI_API_KEY environment variable.")
        sys.exit(1)

    # --- Step 3: Embed ---
    print(f"[3/4] Generating embeddings ...")
    from embedder import generate_embeddings, save_embeddings, set_api_key
    set_api_key(api_key)
    embeddings = generate_embeddings(chunks)
    embeddings_file = output_dir / "embeddings.npz"
    metadata_file = output_dir / "metadata.json"
    save_embeddings(embeddings, chunks, embeddings_file, metadata_file)
    print(f"       Saved embeddings -> {embeddings_file}")

    # --- Step 4: BM25 index ---
    print(f"[4/4] Building BM25 index ...")
    corpus_tokens = []
    chunk_ids = []
    for chunk in chunks:
        tokens = re.sub(r"[^\w\s]", " ", chunk["text"].lower()).split()
        corpus_tokens.append(tokens)
        chunk_ids.append(chunk["chunk_id"])

    bm25_file = output_dir / "bm25_corpus.json"
    with open(bm25_file, "w", encoding="utf-8") as f:
        json.dump({"corpus_tokens": corpus_tokens, "chunk_ids": chunk_ids},
                  f, ensure_ascii=False)
    print(f"       Saved BM25 index -> {bm25_file}")

    print(f"\nDone! All artifacts saved to {output_dir}/")


if __name__ == "__main__":
    main()
