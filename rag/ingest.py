"""Multi-format document extraction with page-level mapping.

Supported formats: PDF, plain text, Markdown.
"""
import pdfplumber
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


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


# --- Backward-compatible helpers ---

def extract_pages(pdf_path: str) -> List[dict]:
    """Legacy API: extract PDF pages as list of dicts.

    Kept for backward compatibility with existing scripts.
    """
    doc = extract(pdf_path)
    return [
        {"page_number": p.page_number, "text": p.text}
        for p in doc.pages
    ]


def get_full_text(pages: List[dict]) -> str:
    """Combine all pages into a single text with page markers."""
    parts = []
    for p in pages:
        parts.append(f"[PAGE {p['page_number']}]\n{p['text']}")
    return "\n\n".join(parts)
