"""OpenAI embedding generation for document chunks."""
import json
import time
import numpy as np
from typing import List, Dict, Optional
from pathlib import Path

from . import config


def _get_client():
    """Lazy-load OpenAI client."""
    from openai import OpenAI
    api_key = config.OPENAI_API_KEY
    if not api_key:
        raise ValueError(
            "OPENAI_API_KEY not set. Either:\n"
            "  1. Set it in .env file in the project root\n"
            "  2. Set the OPENAI_API_KEY environment variable\n"
            "  3. Update config.OPENAI_API_KEY directly"
        )
    return OpenAI(api_key=api_key)


def _build_embedding_text(chunk: Dict) -> str:
    """Build the text to embed, including metadata context.

    Format: "Chapter X: Title > Section: chunk_text"
    This helps the embedding model understand the hierarchical context.
    """
    prefix_parts = []
    if chunk.get("chapter_title"):
        prefix_parts.append(f"Chapter {chunk['chapter_number']}: {chunk['chapter_title']}")
    if chunk.get("section_title"):
        prefix_parts.append(chunk["section_title"])

    prefix = " > ".join(prefix_parts)
    if prefix:
        return f"{prefix}\n\n{chunk['text']}"
    return chunk["text"]


def generate_embeddings(chunks: List[Dict],
                        batch_size: Optional[int] = None) -> np.ndarray:
    """Generate embeddings for all chunks using OpenAI API.

    Args:
        chunks: List of chunk dicts (must have 'text' key)
        batch_size: Number of chunks per API call

    Returns:
        numpy array of shape (num_chunks, embedding_dim)
    """
    client = _get_client()
    batch_size = batch_size or config.EMBEDDING_BATCH_SIZE

    texts = [_build_embedding_text(c) for c in chunks]
    all_embeddings = []

    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        print(f"  Embedding batch {i // batch_size + 1}/"
              f"{(len(texts) - 1) // batch_size + 1} "
              f"({len(batch)} chunks)...")

        try:
            response = client.embeddings.create(
                model=config.EMBEDDING_MODEL,
                input=batch
            )
            batch_embeddings = [item.embedding for item in response.data]
            all_embeddings.extend(batch_embeddings)
        except Exception as e:
            if "rate_limit" in str(e).lower():
                print(f"  Rate limited, waiting 60s...")
                time.sleep(60)
                response = client.embeddings.create(
                    model=config.EMBEDDING_MODEL,
                    input=batch
                )
                batch_embeddings = [item.embedding for item in response.data]
                all_embeddings.extend(batch_embeddings)
            else:
                raise

    return np.array(all_embeddings, dtype=np.float32)


def embed_query(query: str) -> np.ndarray:
    """Embed a single query string.

    Returns:
        numpy array of shape (embedding_dim,)
    """
    client = _get_client()
    response = client.embeddings.create(
        model=config.EMBEDDING_MODEL,
        input=query
    )
    return np.array(response.data[0].embedding, dtype=np.float32)


def save_embeddings(embeddings: np.ndarray, metadata: List[Dict],
                    embeddings_path: Optional[Path] = None,
                    metadata_path: Optional[Path] = None):
    """Save embeddings and metadata to disk."""
    embeddings_path = embeddings_path or config.EMBEDDINGS_FILE
    metadata_path = metadata_path or config.METADATA_FILE

    embeddings_path.parent.mkdir(parents=True, exist_ok=True)

    np.savez_compressed(embeddings_path, embeddings=embeddings)

    # Save metadata (chunk_id, chapter, section, page_range for each vector)
    meta = []
    for chunk in metadata:
        meta.append({
            "chunk_id": chunk["chunk_id"],
            "chapter_number": chunk["chapter_number"],
            "chapter_title": chunk["chapter_title"],
            "section_title": chunk["section_title"],
            "page_range": chunk["page_range"],
            "token_estimate": chunk["token_estimate"]
        })
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)


def load_embeddings(embeddings_path: Optional[Path] = None,
                    metadata_path: Optional[Path] = None):
    """Load embeddings and metadata from disk.

    Returns:
        (embeddings: np.ndarray, metadata: List[Dict])
    """
    embeddings_path = embeddings_path or config.EMBEDDINGS_FILE
    metadata_path = metadata_path or config.METADATA_FILE

    data = np.load(embeddings_path)
    embeddings = data["embeddings"]

    with open(metadata_path, "r", encoding="utf-8") as f:
        metadata = json.load(f)

    return embeddings, metadata
