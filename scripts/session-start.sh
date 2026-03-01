#!/bin/bash

# SessionStart hook: Ensure fablers-agentic-rag settings file exists

PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"
SETTINGS_FILE="$PROJECT_DIR/.claude/fablers-agentic-rag.local.md"
TEMPLATE_FILE="$PLUGIN_ROOT/fablers-rag.template.md"

# Check plugin installation
if [ ! -f "$PLUGIN_ROOT/commands/ask.md" ] || [ ! -f "$PLUGIN_ROOT/skills/ask/SKILL.md" ]; then
  echo '{"continue": true, "systemMessage": "[fablers-agentic-rag] Warning: Plugin files incomplete."}'
  exit 0
fi

# Provision settings file if missing
if [ ! -f "$SETTINGS_FILE" ]; then
  mkdir -p "$PROJECT_DIR/.claude"
  if [ -f "$TEMPLATE_FILE" ]; then
    cp "$TEMPLATE_FILE" "$SETTINGS_FILE"
    echo "{\"continue\": true, \"systemMessage\": \"[fablers-agentic-rag] Settings created at .claude/fablers-agentic-rag.local.md — please set rag_data_path to your RAG data directory (containing chunks.json, embeddings.npz, bm25_corpus.json).\"}"
  else
    echo '{"continue": true, "systemMessage": "[fablers-agentic-rag] Warning: Template not found."}'
  fi
else
  echo '{"continue": true, "systemMessage": "[fablers-agentic-rag] Ready."}'
fi
