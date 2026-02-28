---
name: fablers-rag
description: "RAG system for document retrieval and Q&A. Use when users want to build a RAG pipeline from PDFs, search documents, evaluate retrieval quality, or improve search accuracy. Triggers: RAG, retrieval, document search, embed, chunk, evaluate RAG, hybrid search."
---

# RAG System Skill

A complete RAG (Retrieval-Augmented Generation) pipeline with built-in evaluation and improvement tools.

## Project Location

The RAG system is at `graphrag/rag/` in the workspace. All commands assume working directory is the `graphrag/` folder.

## Prerequisites

```bash
pip install openai rank_bm25 pdfplumber --break-system-packages
```

Set OpenAI API key:
```python
# In rag/config.py, or set environment variable:
export OPENAI_API_KEY="sk-..."
```

## Commands

### 1. Build RAG from PDF

When user says "build RAG", "index this PDF", or "embed this document":

```python
import sys; sys.path.insert(0, '.')
from rag.ingest import extract_pages
from rag.chunker import chunk_document, save_chunks
from rag.embedder import generate_embeddings, save_embeddings
from rag.vector_store import VectorStore

# Step 1: Extract and chunk
pages = extract_pages("path/to/document.pdf")
chunks = chunk_document(pages)
save_chunks(chunks)
print(f"Created {len(chunks)} chunks")

# Step 2: Generate embeddings
embeddings = generate_embeddings(chunks)
save_embeddings(embeddings, chunks)
print(f"Generated {len(embeddings)} embeddings")

# Step 3: Build vector store (verify it works)
store = VectorStore()
store.build(embeddings, chunks)
print("Vector store ready")
```

### 2. Search / Question Answering

When user asks a question about the indexed document:

```python
from rag.retriever import Retriever

retriever = Retriever()
retriever.load()

# Get formatted context for answering
context = retriever.get_context_for_query("user's question here", top_k=5)
```

Then use the context to answer the user's question. Format your response citing the source chunks.

### 3. Evaluate Retrieval Quality

When user says "evaluate", "test quality", or "how good is the RAG":

**Step A: Generate test set (if none exists)**

For each sampled chunk, use this prompt to generate questions:

```python
from rag.eval.testset_generator import sample_chunks_for_eval, get_generation_prompt, save_testset
from rag.chunker import load_chunks

chunks = load_chunks()
sample = sample_chunks_for_eval(chunks, sample_size=30)

# For each chunk in sample, generate questions using the prompt:
for chunk in sample:
    prompt = get_generation_prompt(chunk, num_questions=3)
    # Use this prompt to generate Q&A pairs
    # Parse the JSON response and collect results
```

Save the testset using `save_testset(questions)`.

**Step B: Run evaluation**

```python
from rag.eval.evaluator import evaluate_retrieval, save_eval_results
from rag.eval.testset_generator import load_testset
from rag.retriever import Retriever

retriever = Retriever()
retriever.load()
testset = load_testset()

results = evaluate_retrieval(retriever, testset)
path = save_eval_results(results, label="baseline")
print(f"Results saved to {path}")
print(f"Hit rate@5: {results['metrics']['hit_rate@5']}")
print(f"MRR: {results['metrics']['mrr']}")
```

**Step C: Run diagnostics**

```python
from rag.eval.diagnostics import diagnose_failures, format_report
from rag.chunker import load_chunks

chunks = load_chunks()
report = diagnose_failures(results, chunks)
print(format_report(report))
```

### 4. Improve Search Quality

Based on diagnostic recommendations:

**Enable Hybrid Search** (for recall issues):
```python
# Edit rag/config.py:
HYBRID_SEARCH = True
HYBRID_ALPHA = 0.6  # 0.6 = 60% vector, 40% keyword

# Rebuild BM25 index
from rag.improvements.hybrid_search import BM25Index
from rag.chunker import load_chunks
bm25 = BM25Index()
bm25.build(load_chunks())
bm25.save()
```

**Enable Reranking** (for ranking issues):
```python
# Edit rag/config.py:
RERANKING = True
RERANK_INITIAL_K = 20

# When searching, retriever returns 20 results
# Use the rerank prompt to reorder them:
from rag.improvements.reranker import get_rerank_prompt
prompt = get_rerank_prompt(query, results)
# Evaluate the prompt and reorder results
```

**Adjust Chunking**:
```python
# Edit rag/config.py:
CHUNK_MAX_TOKENS = 600   # Try smaller chunks
CHUNK_OVERLAP_SENTENCES = 3  # More overlap

# Then rebuild: re-chunk → re-embed → re-evaluate
```

### 5. Compare Before/After

```python
from rag.eval.evaluator import compare_evals
from pathlib import Path

result = compare_evals(
    Path("data/eval_results/eval_baseline_TIMESTAMP.json"),
    Path("data/eval_results/eval_hybrid_TIMESTAMP.json")
)
# Shows metric changes for each improvement
```

## Configuration Reference

All settings in `rag/config.py`:

| Setting | Default | Description |
|---------|---------|-------------|
| CHUNK_MAX_TOKENS | 800 | Max tokens per chunk |
| CHUNK_OVERLAP_SENTENCES | 2 | Overlap between split chunks |
| EMBEDDING_MODEL | text-embedding-3-small | OpenAI embedding model |
| TOP_K | 10 | Search results count |
| HYBRID_SEARCH | False | Enable BM25 + vector |
| HYBRID_ALPHA | 0.6 | Vector weight in hybrid |
| RERANKING | False | Enable Claude reranking |

## Architecture

```
PDF → ingest.py → chunker.py → embedder.py → vector_store.py
                                                    ↓
                              query → retriever.py → SearchResults
                                        ↓
                              eval/ → evaluator.py → diagnostics.py
                                        ↓
                              improvements/ → hybrid_search.py, reranker.py
```
