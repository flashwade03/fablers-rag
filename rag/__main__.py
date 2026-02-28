"""CLI entry point for the RAG ingestion pipeline.

Usage:
    python -m rag --document ./mybook.pdf --output-dir ./data
    python -m rag --document ./notes.md --output-dir ./data/notes --skip-embeddings
"""
import argparse
import json
import re
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(
        description="Ingest a document into the RAG pipeline "
                    "(extract → chunk → embed → BM25 index)."
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
    args = parser.parse_args()

    doc_path = Path(args.document)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # --- Step 1: Extract ---
    print(f"[1/4] Extracting text from {doc_path.name} ...")
    from .ingest import extract
    document = extract(str(doc_path))
    print(f"       Extracted {len(document.pages)} page(s), format={document.format}")

    # --- Step 2: Chunk ---
    print(f"[2/4] Chunking document ...")
    from .chunker import chunk_document, save_chunks
    chunks = chunk_document(document)
    chunks_file = output_dir / "chunks.json"
    save_chunks(chunks, chunks_file)
    print(f"       Created {len(chunks)} chunks → {chunks_file}")

    if args.skip_embeddings:
        print("[3/4] Skipped (--skip-embeddings)")
        print("[4/4] Skipped (--skip-embeddings)")
        print("\nDone! Chunks saved. Use without --skip-embeddings to generate embeddings.")
        return

    # --- Step 3: Embed ---
    print(f"[3/4] Generating embeddings ...")
    from .embedder import generate_embeddings, save_embeddings
    embeddings = generate_embeddings(chunks)
    embeddings_file = output_dir / "embeddings.npz"
    metadata_file = output_dir / "metadata.json"
    save_embeddings(embeddings, chunks, embeddings_file, metadata_file)
    print(f"       Saved embeddings → {embeddings_file}")

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
    print(f"       Saved BM25 index → {bm25_file}")

    print(f"\nDone! All artifacts saved to {output_dir}/")


if __name__ == "__main__":
    main()
