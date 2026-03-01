---
name: ask
description: "Agentic RAG pipeline that answers questions about indexed documents using query analysis, hybrid retrieval, evaluation with CRAG validation, and answer synthesis. Triggers: ask question, search document, answer from book, agentic RAG."
---

# Agentic RAG Pipeline

Answer the user's question using a streamlined pipeline with complexity-based branching and CRAG (Corrective RAG) loop.

## Input

The user's question is: **$ARGUMENTS**

## Pipeline

### Step 0: Read Configuration

Read the settings file at `${CLAUDE_PROJECT_DIR}/.claude/fablers-agentic-rag.local.md` (or `.claude/fablers-agentic-rag.local.md` relative to the current project).

Extract from the YAML frontmatter:
- `rag_data_path` — absolute path to the data directory containing `chunks.json`, `embeddings.npz`, and `bm25_corpus.json`
- `openai_api_key` — OpenAI API key for query embedding

If the file doesn't exist, or `rag_data_path` still shows the placeholder `/path/to/data`, or `openai_api_key` is `YOUR_OPENAI_API_KEY`, stop and ask the user to configure it:
> "Please configure `rag_data_path` and `openai_api_key` in `.claude/fablers-agentic-rag.local.md`."

### Step 1: Complexity Classification

Classify the question as **simple** or **complex**:

- **Simple**: Single-topic factual question, definition lookup, "what is X?", "who is Y?", straightforward recall
- **Complex**: Multi-part question, comparison, "for each X, what Y?", analysis, synthesis across topics, cause-and-effect

### Step 2: Query Generation (branching)

#### 2a. Complex Questions → query-analyst agent

Launch the `query-analyst` agent with the user's question:

```
Agent(subagent_type="query-analyst", prompt="Analyze this question and generate optimized search queries:\n\n<question>\n$ARGUMENTS\n</question>")
```

Capture the `SEARCH_QUERIES` from the agent's response. Extract the individual queries as a list.

#### 2b. Simple Questions → direct query generation (no agent)

Generate 2 search queries yourself:
1. A semantically rich version for vector search (rephrase for embedding similarity)
2. A keyword-focused version for BM25 (specific terms, names, concepts)

Format them as:
```
SEARCH_QUERIES:
1. <semantic query>
2. <keyword query>
```

### Step 3: Hybrid Search (direct script execution — not an agent)

Run the search script directly using Bash:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/search.py \
  --data-dir "<rag_data_path from Step 0>" \
  --queries <each query from Step 2, space-separated and quoted> \
  --api-key "<openai_api_key from Step 0>" \
  --top-k 20
```

Capture the `RETRIEVAL_RESULTS` JSON array from stdout.

### Step 4: Evaluation (conditional)

**Skip condition**: If the question is simple AND the top retrieval results have high scores (top result score >= 0.75), you may skip the evaluator agent and directly select the top 5 results. Proceed to Step 5 with VERDICT=SUFFICIENT.

**Otherwise**, launch the `evaluator` agent:

```
Agent(subagent_type="evaluator", prompt="Evaluate these retrieval results: rerank by relevance to the question, select top 5, and validate sufficiency.\n\n<question>\n$ARGUMENTS\n</question>\n\n<retrieval_results>\n{RETRIEVAL_RESULTS JSON from Step 3}\n</retrieval_results>")
```

Capture `RERANKED_TOP_5`, `VERDICT`, `REWRITE_QUERY`, and `TOP_5_CHUNKS`.

Check the `VERDICT`:

- **SUFFICIENT** → proceed to Step 5
- **RETRY_WITH_REWRITE** → go to Step 4a (max 2 retries)
- **INSUFFICIENT** → proceed to Step 5 with the insufficient flag

### Step 4a: CRAG Retry Loop (max 2 times)

If the verdict is RETRY_WITH_REWRITE:

1. Extract the `REWRITE_QUERY` from the evaluator's response
2. Go back to Step 3 with the rewritten query (run search.py with the new query)
3. Then Step 4 again (launch evaluator with new results)

Track the retry count. After 2 retries, treat the current results as the best available and proceed to Step 5 regardless of the verdict.

### Step 5: Answer Synthesis

Launch the `answer-synthesizer` agent with the question, validated passages, and verdict:

```
Agent(subagent_type="answer-synthesizer", prompt="Synthesize a final answer with citations.\n\n<question>\n$ARGUMENTS\n</question>\n\n<verdict>\n{VERDICT from Step 4}\n</verdict>\n\n<passages>\n{TOP_5_CHUNKS — the best available from the last evaluation}\n</passages>")
```

### Step 6: Present the Answer

Display the synthesizer's response directly to the user. The answer should include:
- The synthesized answer with inline `[Source N]` citations
- A sources section with chapter and page references
- If INSUFFICIENT: a note that the answer may be incomplete

## Pipeline Summary

```
Simple questions (1 agent call):
  Skill generates 2 queries → search.py → [skip evaluator] → answer-synthesizer

Complex questions (up to 3 agent calls):
  query-analyst → search.py → evaluator → answer-synthesizer
                                  ↑  RETRY (max 2x)
                                  └── search.py → evaluator
```

## Error Handling

- If any agent fails, log the error and skip to the next reasonable step.
- If retrieval returns 0 results, skip directly to answer synthesis with an INSUFFICIENT verdict.
- The CRAG retry loop is hard-capped at 2 retries to prevent infinite loops.
