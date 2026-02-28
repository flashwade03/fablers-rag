<div align="center">

# fablers-agentic-rag

**Ask your documents. Get a cited answer.**

A Claude Code plugin that runs a full agentic RAG pipeline — query analysis, hybrid retrieval, reranking, CRAG validation, and cited answer synthesis — all orchestrated by Claude agents. Supports PDF, plain text, and Markdown.

[![Claude Code Plugin](https://img.shields.io/badge/Claude_Code-Plugin-blueviolet?style=for-the-badge)](https://claude.ai)
[![Version](https://img.shields.io/badge/version-1.2.0-blue?style=for-the-badge)](#)
[![License: MIT](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](LICENSE)

[English](README.md) | [한국어](README.ko.md) | [日本語](README.ja.md)

</div>

---

## What is this?

You have documents. You have questions. But keyword search is fragile and LLMs hallucinate without sources.

**fablers-agentic-rag** bridges the gap: it chunks your document (PDF, TXT, or Markdown), indexes it with vector + BM25, and deploys a 5-agent pipeline that retrieves, validates, and synthesizes answers with page-level citations.

---

## How it works

```
/ask How does the elemental tetrad relate to game mechanics?
```

```
You ── /ask ──▶ Query Analyst ──▶ Retriever ──▶ Reranker ──▶ Validator ──▶ Synthesizer
                  │                   │              │            │              │
             Decomposes          Hybrid search    Scores &     CRAG check    Cited answer
             into 2-5            (Vector+BM25)    picks top 5  Sufficient?   with [Source N]
             sub-queries         up to 20 results               │
                                                          ┌─────┴──────┐
                                                          │  RETRY?    │
                                                          │  rewrite → │──▶ back to Retriever
                                                          │  (max 2x)  │
                                                          └────────────┘
```

### The 5 Agents

| # | Agent | Role |
|---|-------|------|
| 1 | **Query Analyst** | Decomposes complex questions into 2-5 concrete search queries. Handles "for each X, what Y?" patterns by enumerating known instances. |
| 2 | **Retriever** | Runs hybrid search (vector cosine similarity + BM25 keyword matching) with per-query minimum allocation to ensure diverse coverage. |
| 3 | **Reranker** | LLM-based relevance scoring. Selects the top 5 passages from up to 20 candidates. |
| 4 | **Validator** | CRAG (Corrective RAG) check — are the passages sufficient? If not, rewrites the query and retries (max 2x). |
| 5 | **Answer Synthesizer** | Produces the final answer with inline `[Source N]` citations and a sources section with heading/page references. |

---

## Quick Start

### 1. Install the plugin

```bash
claude --plugin-dir /path/to/fablers-rag/plugin
```

### 2. Prepare your data

Run the ingestion pipeline to generate chunks, embeddings, and BM25 index:

```bash
pip install openai numpy rank_bm25 pdfplumber
python -m rag --document /path/to/your/document.pdf --output-dir ./data
```

Supports `.pdf`, `.txt`, and `.md` files. Use `--skip-embeddings` to test chunking only.

### 3. Configure

Copy the template and fill in your values:

```bash
cp plugin/fablers-rag.template.md .claude/fablers-agentic-rag.local.md
```

Edit `.claude/fablers-agentic-rag.local.md`:

```yaml
rag_data_path: /absolute/path/to/data
openai_api_key: sk-...
```

### 4. Ask

```
/ask What are the key concepts in chapter 3?
/ask How does the author define the main framework, and what tools help evaluate each element?
```

---

## Project Structure

```
fablers-rag/
├── .claude-plugin/
│   ├── plugin.json              # Plugin manifest
│   └── marketplace.json         # Marketplace metadata
├── plugin/
│   ├── agents/
│   │   ├── query-analyst.md     # Query decomposition
│   │   ├── retriever.md         # Hybrid search execution
│   │   ├── reranker.md          # LLM-based reranking
│   │   ├── validator.md         # CRAG validation
│   │   └── answer-synthesizer.md # Cited answer generation
│   ├── commands/
│   │   └── ask.md               # /ask command definition
│   ├── skills/
│   │   └── ask/SKILL.md         # Pipeline orchestration
│   ├── scripts/
│   │   ├── search.py            # Hybrid search engine
│   │   └── session-start.sh     # Session initialization
│   ├── hooks/
│   │   └── hooks.json           # Event hooks
│   └── fablers-rag.template.md  # Config template
├── rag/                          # Ingestion & indexing
│   ├── __main__.py              # CLI entry point
│   ├── ingest.py                # Multi-format extraction (PDF/TXT/MD)
│   ├── chunker.py               # Auto-detect chunking strategy
│   ├── embedder.py
│   ├── vector_store.py
│   ├── retriever.py
│   ├── config.py
│   ├── eval/                    # Evaluation suite
│   └── improvements/            # Search enhancements
├── .env.template
└── .gitignore
```

---

## Key Design Decisions

### Hybrid Search (Vector + BM25)

Pure vector search misses exact terminology. Pure keyword search misses semantics. The hybrid approach (alpha=0.6 vector, 0.4 BM25) captures both.

### Per-Query Minimum Allocation

When 5 sub-queries compete for 20 result slots, dominant queries can crowd out niche topics. Each query is guaranteed at least 2 unique results before remaining slots fill by score.

### CRAG Loop

Not all retrieval attempts succeed. The validator checks passage sufficiency and can trigger up to 2 query rewrites, making the pipeline self-correcting.

---

## Configuration

| Setting | Description |
|---------|-------------|
| `rag_data_path` | Absolute path to the directory containing `chunks.json`, `embeddings.npz`, `bm25_corpus.json` |
| `openai_api_key` | OpenAI API key for `text-embedding-3-small` query embedding |

---

## License

MIT
