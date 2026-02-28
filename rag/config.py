"""Central configuration for the RAG system."""
import os
from pathlib import Path
from dotenv import load_dotenv

# === Paths ===
BASE_DIR = Path(__file__).parent.parent

# Load .env from project root
load_dotenv(BASE_DIR / ".env")
DATA_DIR = BASE_DIR / "data"
EVAL_RESULTS_DIR = DATA_DIR / "eval_results"

# === Chunking ===
CHUNK_MAX_TOKENS = 800          # Max tokens per chunk
CHUNK_OVERLAP_SENTENCES = 2     # Sentence overlap between split chunks
CHARS_PER_TOKEN = 4             # Approximate chars per token (English)

# === Embedding ===
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSION = 1536
EMBEDDING_BATCH_SIZE = 100      # Chunks per API call

# === Retrieval ===
TOP_K = 10                      # Number of results to return

# === Improvement toggles ===
HYBRID_SEARCH = True            # BM25 + vector hybrid
HYBRID_ALPHA = 0.6              # Weight for vector (1-alpha for BM25)
RERANKING = False               # Claude-based reranking
RERANK_INITIAL_K = 20           # Fetch this many before reranking

# === API ===
# Set via: export OPENAI_API_KEY="sk-..." or in .env file
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# === Data files ===
CHUNKS_FILE = DATA_DIR / "chunks.json"
EMBEDDINGS_FILE = DATA_DIR / "embeddings.npz"
METADATA_FILE = DATA_DIR / "metadata.json"
BM25_INDEX_FILE = DATA_DIR / "bm25_corpus.json"
