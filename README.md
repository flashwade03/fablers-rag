<div align="center">

# fablers-agentic-rag

**Ask your documents. Get a cited answer.**

A Claude Code plugin that runs an agentic RAG pipeline — query analysis, hybrid retrieval, evaluation with CRAG validation, and cited answer synthesis — all orchestrated by Claude agents. Supports PDF, plain text, and Markdown.

[![Claude Code Plugin](https://img.shields.io/badge/Claude_Code-Plugin-blueviolet?style=for-the-badge)](https://claude.ai)
[![Version](https://img.shields.io/badge/version-2.0.1-blue?style=for-the-badge)](#)
[![License: MIT](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](LICENSE)

[English](README.md) | [한국어](README.ko.md) | [日本語](README.ja.md)

</div>

---

## What is this?

You have documents. You have questions. But keyword search is fragile and LLMs hallucinate without sources.

**fablers-agentic-rag** bridges the gap: it chunks your document (PDF, TXT, or Markdown), indexes it with vector + BM25, and deploys a streamlined 3-agent pipeline that retrieves, validates, and synthesizes answers with page-level citations.

---

## What's new in v2.0.0

- **Faster**: 3 agents instead of 5 — simple questions use only 1 agent call
- **Simpler structure**: repo root = plugin (no nested `plugin/` directory)
- **New commands**: `/search` for direct search, `/ingest` for document indexing
- **Smarter routing**: complexity-based branching skips unnecessary agents

---

## How it works

```
/ask How does the elemental tetrad relate to game mechanics?
```

**Simple questions** (1 agent call):
```
You ── /ask ──▶ Skill generates 2 queries ──▶ search.py ──▶ Answer Synthesizer
                                                              │
                                                        Cited answer
                                                        with [Source N]
```

**Complex questions** (up to 3 agent calls):
```
You ── /ask ──▶ Query Analyst ──▶ search.py ──▶ Evaluator ──▶ Answer Synthesizer
                  │                                │                │
             Decomposes into              Reranks + CRAG        Cited answer
             2-5 sub-queries              validation            with [Source N]
                                               │
                                         ┌─────┴──────┐
                                         │  RETRY?    │
                                         │  rewrite → │──▶ back to search.py
                                         │  (max 2x)  │
                                         └────────────┘
```

### The 3 Agents

| # | Agent | Role |
|---|-------|------|
| 1 | **Query Analyst** | Decomposes complex questions into 2-5 concrete search queries. Skipped for simple questions. |
| 2 | **Evaluator** | Reranks retrieved passages by relevance (top 5) + CRAG validation. Can trigger query rewrites (max 2x). |
| 3 | **Answer Synthesizer** | Produces the final answer with inline `[Source N]` citations and a sources section. |

---

## Quick Start

### 1. Install the plugin

In Claude Code, add the marketplace and install:
```
/plugin marketplace add flashwade03/fablers-rag
/plugin install fablers-agentic-rag@flashwade03/fablers-rag
```

### 2. Prepare your data

Install dependencies and run the ingestion pipeline:

```bash
pip install openai numpy rank_bm25 pdfplumber
cd scripts && python3 ingest.py --document /path/to/your/document.pdf --output-dir ../data
```

Or use the `/ingest` command after installing the plugin.

Supports `.pdf`, `.txt`, and `.md` files. Use `--skip-embeddings` to test chunking only.

### 3. Configure

On first session start, the plugin creates `.claude/fablers-agentic-rag.local.md`. Edit it:

```yaml
rag_data_path: /absolute/path/to/data
openai_api_key: sk-...
```

### 4. Ask

```
/ask What are the key concepts in chapter 3?
/ask How does the author define the main framework, and what tools help evaluate each element?
```

### Other commands

```
/search What is game design?        # Direct hybrid search, raw results
/ingest /path/to/new-document.pdf   # Index a new document
```

---

## Project Structure

```
fablers-rag/                          ← repo root = plugin
├── .claude-plugin/
│   ├── plugin.json                   # Plugin manifest (v2.0.0)
│   └── marketplace.json              # Marketplace metadata
├── agents/
│   ├── query-analyst.md              # Query decomposition
│   ├── evaluator.md                  # Reranking + CRAG validation
│   └── answer-synthesizer.md         # Cited answer generation
├── commands/
│   ├── ask.md                        # /ask command
│   ├── search.md                     # /search command
│   └── ingest.md                     # /ingest command
├── skills/
│   └── ask/SKILL.md                  # Pipeline orchestration
├── scripts/
│   ├── search.py                     # Hybrid search engine
│   ├── ingest.py                     # Document ingestion pipeline
│   ├── chunker.py                    # Auto-detect chunking strategy
│   ├── embedder.py                   # OpenAI embeddings
│   ├── config.py                     # Chunking/embedding settings
│   └── session-start.sh              # Session initialization
├── hooks/
│   └── hooks.json                    # Event hooks
├── fablers-rag.template.md           # Config template
└── SKILL.md                          # Root skill
```

---

## Key Design Decisions

### Hybrid Search (Vector + BM25)

Pure vector search misses exact terminology. Pure keyword search misses semantics. The hybrid approach (alpha=0.6 vector, 0.4 BM25) captures both.

### Complexity-Based Branching

Simple factual questions skip the query analyst and evaluator, reducing latency from 5 agent calls to 1. Complex multi-part questions get the full pipeline.

### CRAG Loop

Not all retrieval attempts succeed. The evaluator checks passage sufficiency and can trigger up to 2 query rewrites, making the pipeline self-correcting.

---

## Configuration

| Setting | Description |
|---------|-------------|
| `rag_data_path` | Absolute path to the directory containing `chunks.json`, `embeddings.npz`, `bm25_corpus.json` |
| `openai_api_key` | OpenAI API key for `text-embedding-3-small` query embedding |

---

## License

MIT
