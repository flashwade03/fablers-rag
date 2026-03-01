---
name: fablers-rag
description: "RAG system for document retrieval and Q&A. Use when users want to build a RAG pipeline from PDFs/TXT/Markdown, search documents, or run the agentic Q&A pipeline. Triggers: RAG, retrieval, document search, embed, chunk, hybrid search, ingest."
---

# RAG System Skill

A complete RAG (Retrieval-Augmented Generation) pipeline with agentic Q&A. Supports PDF, plain text, and Markdown documents.

## Prerequisites

```bash
pip install openai numpy rank_bm25 pdfplumber
```

Set OpenAI API key:
```bash
export OPENAI_API_KEY="sk-..."
```

## Commands

### 1. Ingest a Document

When user says "build RAG", "index this document", or "embed this file":

```bash
cd scripts && python3 ingest.py --document /path/to/document.pdf --output-dir ./data

# Markdown or text files also supported
cd scripts && python3 ingest.py --document notes.md --output-dir ./data/notes

# Chunking only (skip embeddings, useful for testing)
cd scripts && python3 ingest.py --document notes.md --output-dir ./data/notes --skip-embeddings
```

Or use the `/ingest` command.

### 2. Search

Direct hybrid search against the index:

```bash
python3 scripts/search.py \
  --data-dir /path/to/data \
  --queries "your query here" \
  --api-key "$OPENAI_API_KEY" \
  --top-k 10
```

Or use the `/search` command.

### 3. Ask a Question (Agentic RAG)

Use the `/ask` command to run the full agentic pipeline:

```
/ask What are the key concepts in chapter 3?
```

This runs a 3-agent pipeline:
1. **Query Analyst** — Decomposes complex questions into search queries (skipped for simple questions)
2. **Evaluator** — Reranks results and validates sufficiency with CRAG (skipped when results are clearly relevant)
3. **Answer Synthesizer** — Produces cited answers with `[Source N]` references

## Configuration

Edit `scripts/config.py` for chunking and embedding settings:

| Setting | Default | Description |
|---------|---------|-------------|
| CHUNK_MAX_TOKENS | 800 | Max tokens per chunk |
| CHUNK_OVERLAP_SENTENCES | 2 | Overlap between split chunks |
| EMBEDDING_MODEL | text-embedding-3-small | OpenAI embedding model |
| EMBEDDING_BATCH_SIZE | 100 | Chunks per API call |

## Architecture

```
PDF/TXT/MD → ingest.py → chunker.py → embedder.py
              (extract)   (auto-detect     ↓
                           strategy)   search.py (hybrid: vector + BM25)
                                           ↓
                                     agents/ (query-analyst, evaluator, answer-synthesizer)
```
