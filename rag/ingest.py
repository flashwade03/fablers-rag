"""PDF text extraction with page-level mapping."""
import pdfplumber
from pathlib import Path
from typing import List, Dict


def extract_pages(pdf_path: str) -> List[Dict]:
    """Extract text from each page of a PDF.

    Returns:
        List of dicts with keys: page_number, text
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            if text.strip():
                pages.append({
                    "page_number": i + 1,
                    "text": text.strip()
                })

    return pages


def get_full_text(pages: List[Dict]) -> str:
    """Combine all pages into a single text with page markers."""
    parts = []
    for p in pages:
        parts.append(f"[PAGE {p['page_number']}]\n{p['text']}")
    return "\n\n".join(parts)
