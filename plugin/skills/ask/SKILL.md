---
name: ask
description: "Agentic RAG pipeline that answers questions about indexed documents using query analysis, hybrid retrieval, Claude-based reranking, CRAG validation, and answer synthesis. Triggers: ask question, search document, answer from book, agentic RAG."
---

# Agentic RAG Pipeline

Answer the user's question using a multi-agent pipeline with CRAG (Corrective RAG) loop.

## Input

The user's question is: **$ARGUMENTS**

## Pipeline

Execute the following steps sequentially. Each agent returns its result as text — pass the relevant output to the next agent as part of its prompt.

### Step 0: Read Configuration

Read the settings file at `${CLAUDE_PROJECT_DIR}/.claude/fablers-agentic-rag.local.md` (or `.claude/fablers-agentic-rag.local.md` relative to the current project).

Extract from the YAML frontmatter:
- `rag_data_path` — absolute path to the data directory containing `chunks.json`, `embeddings.npz`, and `bm25_corpus.json`
- `openai_api_key` — OpenAI API key for query embedding

If the file doesn't exist, or `rag_data_path` still shows the placeholder `/path/to/data`, or `openai_api_key` is `YOUR_OPENAI_API_KEY`, stop and ask the user to configure it:
> "Please configure `rag_data_path` and `openai_api_key` in `.claude/fablers-agentic-rag.local.md`."

### Step 1: Query Analysis

Launch the `query-analyst` agent with the user's question.

```
Agent(subagent_type="query-analyst", prompt="Analyze this question and generate optimized search queries:\n\n<question>\n$ARGUMENTS\n</question>")
```

Capture the `SEARCH_QUERIES` from the agent's response.

### Step 2: Retrieval

Launch the `retriever` agent with the search queries from Step 1 **and the `rag_data_path` + `openai_api_key` from Step 0**.

```
Agent(subagent_type="retriever", prompt="Execute these search queries against the RAG index and return merged results as JSON.\n\n<rag_data_path>\n{rag_data_path from Step 0}\n</rag_data_path>\n\n<openai_api_key>\n{openai_api_key from Step 0}\n</openai_api_key>\n\n<search_queries>\n{SEARCH_QUERIES from Step 1}\n</search_queries>")
```

Capture the `RETRIEVAL_RESULTS` JSON array.

### Step 3: Reranking

Launch the `reranker` agent with the original question and up to 20 retrieval results.

```
Agent(subagent_type="reranker", prompt="Rerank these retrieval results (up to 20) by relevance to the question and select the top 5.\n\n<question>\n$ARGUMENTS\n</question>\n\n<retrieval_results>\n{RETRIEVAL_RESULTS JSON from Step 2}\n</retrieval_results>")
```

Capture the `RERANKED_RESULTS` and `TOP_5_CHUNKS`.

### Step 4: CRAG Validation

Launch the `validator` agent with the original question and reranked top-5.

```
Agent(subagent_type="validator", prompt="Validate whether these passages are sufficient to answer the question.\n\n<question>\n$ARGUMENTS\n</question>\n\n<top_5_passages>\n{TOP_5_CHUNKS from Step 3}\n</top_5_passages>")
```

Check the `VERDICT`:

- **SUFFICIENT** → proceed to Step 5
- **RETRY_WITH_REWRITE** → go to Step 4a (max 2 retries)
- **INSUFFICIENT** → proceed to Step 5 with the insufficient flag

### Step 4a: CRAG Retry Loop (max 2 times)

If the verdict is RETRY_WITH_REWRITE:

1. Extract the `REWRITE_QUERY` from the validator's response
2. Go back to Step 2 with the rewritten query (launch retriever with the new query)
3. Then Step 3 (rerank the new results)
4. Then Step 4 (validate again)

Track the retry count. After 2 retries, treat the current results as the best available and proceed to Step 5 regardless of the verdict.

### Step 5: Answer Synthesis

Launch the `answer-synthesizer` agent with the question, validated passages, and verdict.

```
Agent(subagent_type="answer-synthesizer", prompt="Synthesize a final answer with citations.\n\n<question>\n$ARGUMENTS\n</question>\n\n<verdict>\n{VERDICT from Step 4}\n</verdict>\n\n<passages>\n{TOP_5_CHUNKS — the best available from the last successful reranking}\n</passages>")
```

### Step 6: Present the Answer

Display the synthesizer's response directly to the user. The answer should include:
- The synthesized answer with inline `[Source N]` citations
- A sources section with chapter and page references
- If INSUFFICIENT: a note that the answer may be incomplete

## Error Handling

- If any agent fails, log the error and skip to the next reasonable step.
- If retrieval returns 0 results, skip directly to answer synthesis with an INSUFFICIENT verdict.
- The CRAG retry loop is hard-capped at 2 retries to prevent infinite loops.
