<div align="center">

# fablers-agentic-rag

**ドキュメントに聞こう。引用付きの回答を得よう。**

クエリ分析、ハイブリッド検索、評価とCRAG検証、引用付き回答合成まで — Claude エージェントがオーケストレーションするAgentic RAGパイプラインプラグイン。PDF、テキスト、Markdownに対応。

[![Claude Code Plugin](https://img.shields.io/badge/Claude_Code-Plugin-blueviolet?style=for-the-badge)](https://claude.ai)
[![Version](https://img.shields.io/badge/version-2.0.0-blue?style=for-the-badge)](#)
[![License: MIT](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](LICENSE)

[English](README.md) | [한국어](README.ko.md) | [日本語](README.ja.md)

</div>

---

## これは何？

ドキュメントがあり、質問がある — でもキーワード検索は不正確で、LLMはソースなしに幻覚します。

**fablers-agentic-rag**がそのギャップを埋めます：ドキュメント（PDF、TXT、Markdown）をチャンキングし、ベクトル + BM25でインデックス化し、効率化された3エージェントパイプラインが検索、検証、ページレベル引用付きの回答を合成します。

---

## v2.0.0の変更点

- **高速化**: 5エージェント → 3エージェント — シンプルな質問は1回のエージェント呼び出しのみ
- **シンプルな構造**: リポルート = プラグイン（ネストされた`plugin/`ディレクトリを削除）
- **新コマンド**: `/search`で直接検索、`/ingest`でドキュメントインデックス化
- **スマートルーティング**: 複雑度ベースの分岐で不要なエージェントをスキップ

---

## 動作方式

```
/ask エレメンタルテトラッドとゲームメカニクスの関係は？
```

**シンプルな質問**（エージェント1回呼び出し）：
```
You ── /ask ──▶ スキルが2クエリ生成 ──▶ search.py ──▶ Answer Synthesizer
                                                        │
                                                  引用付き回答
                                                  [Source N]付き
```

**複雑な質問**（エージェント最大3回呼び出し）：
```
You ── /ask ──▶ Query Analyst ──▶ search.py ──▶ Evaluator ──▶ Answer Synthesizer
                  │                                │                │
             2-5個のサブ                     リランキング+CRAG   引用付き回答
             クエリに分解                     検証             [Source N]付き
                                                   │
                                             ┌─────┴──────┐
                                             │  リトライ？  │
                                             │  クエリ書換え│──▶ search.pyへ戻る
                                             │  (最大2回)  │
                                             └────────────┘
```

### 3つのエージェント

| # | エージェント | 役割 |
|---|------------|------|
| 1 | **Query Analyst** | 複合質問を2-5個の具体的な検索クエリに分解。シンプルな質問ではスキップ。 |
| 2 | **Evaluator** | 検索結果のリランキング（上位5件） + CRAG検証。クエリ書き換えをトリガー可能（最大2回）。 |
| 3 | **Answer Synthesizer** | インライン`[Source N]`引用とソースセクションを含む最終回答を生成。 |

---

## クイックスタート

### 1. プラグインインストール

Claude Codeでマーケットプレイスを追加してインストール：
```
/plugin marketplace add flashwade03/fablers-rag
/plugin install fablers-agentic-rag@flashwade03/fablers-rag
```

### 2. データ準備

依存関係をインストールしてインジェスションパイプラインを実行：

```bash
pip install openai numpy rank_bm25 pdfplumber
cd scripts && python3 ingest.py --document /path/to/your/document.pdf --output-dir ../data
```

またはプラグインインストール後に`/ingest`コマンドを使用してください。

`.pdf`、`.txt`、`.md`ファイルに対応。`--skip-embeddings`でチャンキングのみテスト可能。

### 3. 設定

初回セッション開始時にプラグインが`.claude/fablers-agentic-rag.local.md`を作成します。編集：

```yaml
rag_data_path: /absolute/path/to/data
openai_api_key: sk-...
```

### 4. 質問する

```
/ask 第3章の主要な概念は何ですか？
/ask 著者が定義した主要なフレームワークは何で、各要素を評価するツールは？
```

### その他のコマンド

```
/search ゲームデザインとは？             # 直接ハイブリッド検索、生結果
/ingest /path/to/new-document.pdf      # 新しいドキュメントをインデックス化
```

---

## プロジェクト構造

```
fablers-rag/                          ← リポルート = プラグイン
├── .claude-plugin/
│   ├── plugin.json                   # プラグインマニフェスト（v2.0.0）
│   └── marketplace.json              # マーケットプレイスメタデータ
├── agents/
│   ├── query-analyst.md              # クエリ分解
│   ├── evaluator.md                  # リランキング + CRAG検証
│   └── answer-synthesizer.md         # 引用回答生成
├── commands/
│   ├── ask.md                        # /askコマンド
│   ├── search.md                     # /searchコマンド
│   └── ingest.md                     # /ingestコマンド
├── skills/
│   └── ask/SKILL.md                  # パイプラインオーケストレーション
├── scripts/
│   ├── search.py                     # ハイブリッド検索エンジン
│   ├── ingest.py                     # ドキュメントインジェスションパイプライン
│   ├── chunker.py                    # 自動検出チャンキング戦略
│   ├── embedder.py                   # OpenAIエンベディング
│   ├── config.py                     # チャンキング/エンベディング設定
│   └── session-start.sh              # セッション初期化
├── hooks/
│   └── hooks.json                    # イベントフック
├── fablers-rag.template.md           # 設定テンプレート
└── SKILL.md                          # ルートスキル
```

---

## 主要な設計判断

### ハイブリッド検索（Vector + BM25）

純粋なベクトル検索は正確な用語を見落とします。純粋なキーワード検索はセマンティクスを見落とします。ハイブリッド方式（alpha=0.6ベクトル、0.4 BM25）が両方をカバーします。

### 複雑度ベースの分岐

シンプルなファクト質問はクエリ分析と評価をスキップし、5回のエージェント呼び出しを1回に削減してレイテンシを改善します。複合マルチパート質問は完全なパイプラインを使用します。

### CRAGループ

すべての検索が成功するわけではありません。Evaluatorがパッセージの十分性をチェックし、最大2回のクエリ書き換えをトリガーでき、パイプラインが自己修正します。

---

## 設定

| 設定 | 説明 |
|------|------|
| `rag_data_path` | `chunks.json`、`embeddings.npz`、`bm25_corpus.json`があるディレクトリの絶対パス |
| `openai_api_key` | `text-embedding-3-small`クエリエンベディング用OpenAI APIキー |

---

## ライセンス

MIT
