---
rag_data_path: /path/to/data
openai_api_key: YOUR_OPENAI_API_KEY
---

# Fablers Agentic RAG Configuration

## Settings

### `rag_data_path` (required)

Absolute path to the data directory containing the RAG indexes:
- `chunks.json` — chunked document text
- `embeddings.npz` — vector embeddings
- `bm25_corpus.json` — BM25 keyword index

Example:
```yaml
rag_data_path: /Volumes/FablersBackup/Projects/fablers-rag/data
```

### `openai_api_key` (required)

OpenAI API key for query embedding (`text-embedding-3-small`). Each search query is embedded via the OpenAI API to compute vector similarity against stored chunk embeddings.

```yaml
openai_api_key: sk-...
```

## How it works

The `/ask <question>` command runs a streamlined 3-agent pipeline with complexity branching:

**Simple questions** (1 agent call):
1. Skill generates 2 search queries directly
2. `search.py` runs hybrid search (vector + BM25)
3. **Answer Synthesizer** produces a cited answer

**Complex questions** (up to 3 agent calls):
1. **Query Analyst** — Rewrites your question into optimized search queries
2. `search.py` runs hybrid search on the data at `rag_data_path`
3. **Evaluator** — Scores top 5 passages + CRAG validation (sufficient? retry? insufficient?)
4. **Answer Synthesizer** — Produces a cited answer with `[Source N]` references

Additional commands:
- `/search <query>` — Run a direct hybrid search and see raw results
- `/ingest <file>` — Index a new document (PDF, TXT, or Markdown)
