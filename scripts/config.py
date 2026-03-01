"""Central configuration for the RAG ingestion pipeline."""

# === Chunking ===
CHUNK_MAX_TOKENS = 800          # Max tokens per chunk
CHUNK_OVERLAP_SENTENCES = 2     # Sentence overlap between split chunks
CHARS_PER_TOKEN = 4             # Approximate chars per token (English)

# === Embedding ===
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSION = 1536
EMBEDDING_BATCH_SIZE = 100      # Chunks per API call
