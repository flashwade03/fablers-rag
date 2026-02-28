<div align="center">

# fablers-agentic-rag

**ドキュメントに聞こう。引用付きの回答を得よう。**

クエリ分析、ハイブリッド検索、リランキング、CRAG検証、引用付き回答合成まで — Claude エージェントがオーケストレーションするAgentic RAGパイプラインプラグイン。PDF、テキスト、Markdownに対応。

[![Claude Code Plugin](https://img.shields.io/badge/Claude_Code-Plugin-blueviolet?style=for-the-badge)](https://claude.ai)
[![Version](https://img.shields.io/badge/version-1.2.0-blue?style=for-the-badge)](#)
[![License: MIT](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](LICENSE)

[English](README.md) | [한국어](README.ko.md) | [日本語](README.ja.md)

</div>

---

## これは何？

ドキュメントがあり、質問がある — でもキーワード検索は不正確で、LLMはソースなしに幻覚します。

**fablers-agentic-rag**がそのギャップを埋めます：ドキュメント（PDF、TXT、Markdown）をチャンキングし、ベクトル + BM25でインデックス化し、5つのエージェントパイプラインが検索、検証、ページレベル引用付きの回答を合成します。

---

## 動作方式

```
/ask エレメンタルテトラッドとゲームメカニクスの関係は？
```

```
You ── /ask ──▶ Query Analyst ──▶ Retriever ──▶ Reranker ──▶ Validator ──▶ Synthesizer
                  │                   │              │            │              │
             2-5個のサブ        ハイブリッド検索    スコアリング&  CRAG検証     引用付き回答
             クエリに分解       (ベクトル+BM25)    上位5件選別   十分か？     [Source N]付き
                               最大20件の結果                    │
                                                          ┌─────┴──────┐
                                                          │  リトライ？  │
                                                          │  クエリ書換え│──▶ Retrieverへ戻る
                                                          │  (最大2回)  │
                                                          └────────────┘
```

### 5つのエージェント

| # | エージェント | 役割 |
|---|------------|------|
| 1 | **Query Analyst** | 複合質問を2-5個の具体的な検索クエリに分解。「各Xについて、Yは？」パターンをインスタンス列挙で処理。 |
| 2 | **Retriever** | ハイブリッド検索（ベクトルコサイン類似度 + BM25キーワードマッチング）。クエリ別最小割当で多様なカバレッジを保証。 |
| 3 | **Reranker** | LLMベースの関連性スコアリング。最大20件の候補から上位5件のパッセージを選別。 |
| 4 | **Validator** | CRAG（Corrective RAG）検証 — パッセージは十分か？不十分ならクエリを書き換えてリトライ（最大2回）。 |
| 5 | **Answer Synthesizer** | インライン`[Source N]`引用と見出し/ページ参照を含む最終回答を生成。 |

---

## クイックスタート

### 1. プラグインインストール

Claude Codeでマーケットプレイスを追加してインストール：
```
/plugin marketplace add flashwade03/fablers-rag
/plugin install fablers-agentic-rag@flashwade03/fablers-rag
```

### 2. データ準備

インジェスションパイプラインを実行して、チャンク、エンベディング、BM25インデックスを生成：

```bash
pip install openai numpy rank_bm25 pdfplumber
python -m rag --document /path/to/your/document.pdf --output-dir ./data
```

`.pdf`、`.txt`、`.md`ファイルに対応。`--skip-embeddings`でチャンキングのみテスト可能。

### 3. 設定

テンプレートをコピーして値を設定：

```bash
cp plugin/fablers-rag.template.md .claude/fablers-agentic-rag.local.md
```

`.claude/fablers-agentic-rag.local.md`を編集：

```yaml
rag_data_path: /absolute/path/to/data
openai_api_key: sk-...
```

### 4. 質問する

```
/ask 第3章の主要な概念は何ですか？
/ask 著者が定義した主要なフレームワークは何で、各要素を評価するツールは？
```

---

## プロジェクト構造

```
fablers-rag/
├── .claude-plugin/
│   ├── plugin.json              # プラグインマニフェスト
│   └── marketplace.json         # マーケットプレイスメタデータ
├── plugin/
│   ├── agents/
│   │   ├── query-analyst.md     # クエリ分解
│   │   ├── retriever.md         # ハイブリッド検索実行
│   │   ├── reranker.md          # LLMベースリランキング
│   │   ├── validator.md         # CRAG検証
│   │   └── answer-synthesizer.md # 引用回答生成
│   ├── commands/
│   │   └── ask.md               # /askコマンド定義
│   ├── skills/
│   │   └── ask/SKILL.md         # パイプラインオーケストレーション
│   ├── scripts/
│   │   ├── search.py            # ハイブリッド検索エンジン
│   │   └── session-start.sh     # セッション初期化
│   ├── hooks/
│   │   └── hooks.json           # イベントフック
│   └── fablers-rag.template.md  # 設定テンプレート
├── rag/                          # インジェスション & インデックス化
│   ├── __main__.py              # CLIエントリポイント
│   ├── ingest.py                # マルチフォーマット抽出（PDF/TXT/MD）
│   ├── chunker.py               # 自動検出チャンキング戦略
│   ├── embedder.py
│   ├── vector_store.py
│   ├── retriever.py
│   ├── config.py
│   ├── eval/                    # 評価スイート
│   └── improvements/            # 検索改善
├── .env.template
└── .gitignore
```

---

## 主要な設計判断

### ハイブリッド検索（Vector + BM25）

純粋なベクトル検索は正確な用語を見落とします。純粋なキーワード検索はセマンティクスを見落とします。ハイブリッド方式（alpha=0.6ベクトル、0.4 BM25）が両方をカバーします。

### クエリ別最小割当

5つのサブクエリが20件の結果スロットを競う時、支配的なクエリがニッチトピックを押し出す可能性があります。各クエリは最低2件のユニーク結果を保証され、残りのスロットはスコア順で埋められます。

### CRAGループ

すべての検索が成功するわけではありません。Validatorがパッセージの十分性をチェックし、最大2回のクエリ書き換えをトリガーでき、パイプラインが自己修正します。

---

## 設定

| 設定 | 説明 |
|------|------|
| `rag_data_path` | `chunks.json`、`embeddings.npz`、`bm25_corpus.json`があるディレクトリの絶対パス |
| `openai_api_key` | `text-embedding-3-small`クエリエンベディング用OpenAI APIキー |

---

## ライセンス

MIT
