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

The `/ask <question>` command runs a 5-agent pipeline:

1. **Query Analyst** — Rewrites your question into optimized search queries
2. **Retriever** — Runs hybrid search (vector + BM25) on the data at `rag_data_path`
3. **Reranker** — Scores and picks the top 5 most relevant passages
4. **Validator** — CRAG check: sufficient? retry? insufficient?
5. **Answer Synthesizer** — Produces a cited answer from the validated passages
