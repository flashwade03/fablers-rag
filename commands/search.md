---
name: search
description: Run a direct hybrid search against the RAG index and return raw results.
argument-hint: "<query>"
---

# /search Command

Run a direct hybrid search (vector + BM25) against the indexed document.

## Steps

### 1. Read Configuration

Read the settings file at `${CLAUDE_PROJECT_DIR}/.claude/fablers-agentic-rag.local.md`.

Extract from the YAML frontmatter:
- `rag_data_path` — absolute path to the data directory
- `openai_api_key` — OpenAI API key for query embedding

If the file doesn't exist or values are placeholders, stop and ask the user to configure it.

### 2. Execute Search

Run the search script directly:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/search.py \
  --data-dir "<rag_data_path>" \
  --queries "$ARGUMENTS" \
  --api-key "<openai_api_key>" \
  --top-k 10
```

### 3. Return Results

Display the raw JSON results to the user. Include:
- Number of chunks retrieved
- Each chunk's `chunk_id`, `score`, `heading`, and a text preview (first 200 chars)
