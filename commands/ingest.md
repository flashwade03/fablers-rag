---
name: ingest
description: Ingest a document (PDF, TXT, or Markdown) into the RAG index.
argument-hint: "<file-path>"
---

# /ingest Command

Ingest a document into the RAG pipeline to create searchable chunks, embeddings, and BM25 index.

## Steps

### 1. Check Dependencies

Verify required Python packages are installed:

```bash
python3 -c "import pdfplumber, openai, numpy, rank_bm25" 2>/dev/null
```

If missing, inform the user:
> Install required packages: `pip install openai numpy rank_bm25 pdfplumber`

### 2. Read Configuration

Read `${CLAUDE_PROJECT_DIR}/.claude/fablers-agentic-rag.local.md` and extract:
- `openai_api_key` — for embedding generation
- `rag_data_path` — default output directory

### 3. Execute Ingestion

Run the ingestion script, passing the settings file path so it reads the API key directly:

```bash
cd ${CLAUDE_PLUGIN_ROOT}/scripts && \
python3 ingest.py \
  --document "$ARGUMENTS" \
  --output-dir "<rag_data_path or ./data>" \
  --settings "${CLAUDE_PROJECT_DIR}/.claude/fablers-agentic-rag.local.md"
```

If the user didn't specify an output directory, use the `rag_data_path` from the settings file, or default to `./data`.

### 4. Report Results

After ingestion completes, report:
- Number of pages extracted
- Number of chunks created
- Whether embeddings and BM25 index were generated
- The output directory path

Remind the user to update `rag_data_path` in `.claude/fablers-agentic-rag.local.md` if needed.
