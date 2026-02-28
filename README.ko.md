<div align="center">

# fablers-agentic-rag

**문서에게 물어보세요. 출처가 달린 답변을 받으세요.**

쿼리 분석, 하이브리드 검색, 리랭킹, CRAG 검증, 인용 답변 합성까지 — Claude 에이전트가 오케스트레이션하는 Agentic RAG 파이프라인 플러그인. PDF, 텍스트, 마크다운 지원.

[![Claude Code Plugin](https://img.shields.io/badge/Claude_Code-Plugin-blueviolet?style=for-the-badge)](https://claude.ai)
[![Version](https://img.shields.io/badge/version-1.2.0-blue?style=for-the-badge)](#)
[![License: MIT](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](LICENSE)

[English](README.md) | [한국어](README.ko.md) | [日本語](README.ja.md)

</div>

---

## 이게 뭔가요?

문서는 있고, 질문도 있는데 — 키워드 검색은 부정확하고 LLM은 출처 없이 환각합니다.

**fablers-agentic-rag**가 그 간극을 메웁니다: 문서(PDF, TXT, 마크다운)를 청킹하고, 벡터 + BM25로 인덱싱한 뒤, 5개 에이전트 파이프라인이 검색하고, 검증하고, 페이지 단위 인용이 달린 답변을 합성합니다.

---

## 작동 방식

```
/ask 엘리멘탈 테트라드와 게임 메카닉스의 관계는?
```

```
You ── /ask ──▶ Query Analyst ──▶ Retriever ──▶ Reranker ──▶ Validator ──▶ Synthesizer
                  │                   │              │            │              │
             2-5개 하위        하이브리드 검색     스코어링 &   CRAG 검증    인용된 답변
             쿼리로 분해       (벡터+BM25)        상위 5개 선별  충분한가?   [Source N] 포함
                               최대 20개 결과                    │
                                                          ┌─────┴──────┐
                                                          │  재시도?    │
                                                          │  쿼리 재작성│──▶ Retriever로 복귀
                                                          │  (최대 2회) │
                                                          └────────────┘
```

### 5개 에이전트

| # | 에이전트 | 역할 |
|---|---------|------|
| 1 | **Query Analyst** | 복합 질문을 2-5개 구체적 검색 쿼리로 분해. "X 각각에 대해 Y는?" 패턴을 인스턴스 나열로 처리. |
| 2 | **Retriever** | 하이브리드 검색 (벡터 코사인 유사도 + BM25 키워드 매칭). 쿼리별 최소 할당으로 다양한 커버리지 보장. |
| 3 | **Reranker** | LLM 기반 관련성 스코어링. 최대 20개 후보에서 상위 5개 패시지 선별. |
| 4 | **Validator** | CRAG (Corrective RAG) 검증 — 패시지가 충분한가? 아니면 쿼리를 재작성해서 재시도 (최대 2회). |
| 5 | **Answer Synthesizer** | 인라인 `[Source N]` 인용과 헤딩/페이지 참조가 포함된 최종 답변 생성. |

---

## 빠른 시작

### 1. 플러그인 설치

```bash
claude plugin install fablers-agentic-rag
```

### 2. 데이터 준비

인제스션 파이프라인을 실행해서 청크, 임베딩, BM25 인덱스를 생성합니다:

```bash
pip install openai numpy rank_bm25 pdfplumber
python -m rag --document /path/to/your/document.pdf --output-dir ./data
```

`.pdf`, `.txt`, `.md` 파일을 지원합니다. `--skip-embeddings`로 청킹만 테스트할 수 있습니다.

### 3. 설정

템플릿을 복사하고 값을 채웁니다:

```bash
cp plugin/fablers-rag.template.md .claude/fablers-agentic-rag.local.md
```

`.claude/fablers-agentic-rag.local.md` 편집:

```yaml
rag_data_path: /absolute/path/to/data
openai_api_key: sk-...
```

### 4. 질문하기

```
/ask 3장의 핵심 개념은 무엇인가?
/ask 저자가 정의한 주요 프레임워크는 무엇이고, 각 요소를 평가하는 도구는?
```

---

## 프로젝트 구조

```
fablers-rag/
├── .claude-plugin/
│   ├── plugin.json              # 플러그인 매니페스트
│   └── marketplace.json         # 마켓플레이스 메타데이터
├── plugin/
│   ├── agents/
│   │   ├── query-analyst.md     # 쿼리 분해
│   │   ├── retriever.md         # 하이브리드 검색 실행
│   │   ├── reranker.md          # LLM 기반 리랭킹
│   │   ├── validator.md         # CRAG 검증
│   │   └── answer-synthesizer.md # 인용 답변 생성
│   ├── commands/
│   │   └── ask.md               # /ask 커맨드 정의
│   ├── skills/
│   │   └── ask/SKILL.md         # 파이프라인 오케스트레이션
│   ├── scripts/
│   │   ├── search.py            # 하이브리드 검색 엔진
│   │   └── session-start.sh     # 세션 초기화
│   ├── hooks/
│   │   └── hooks.json           # 이벤트 훅
│   └── fablers-rag.template.md  # 설정 템플릿
├── rag/                          # 인제스션 & 인덱싱
│   ├── __main__.py              # CLI 진입점
│   ├── ingest.py                # 멀티 포맷 추출 (PDF/TXT/MD)
│   ├── chunker.py               # 자동 감지 청킹 전략
│   ├── embedder.py
│   ├── vector_store.py
│   ├── retriever.py
│   ├── config.py
│   ├── eval/                    # 평가 스위트
│   └── improvements/            # 검색 개선
├── .env.template
└── .gitignore
```

---

## 핵심 설계 결정

### 하이브리드 검색 (Vector + BM25)

순수 벡터 검색은 정확한 용어를 놓칩니다. 순수 키워드 검색은 의미를 놓칩니다. 하이브리드 방식(alpha=0.6 벡터, 0.4 BM25)이 둘 다 잡습니다.

### 쿼리별 최소 할당

5개 서브 쿼리가 20개 결과 슬롯을 두고 경쟁할 때, 지배적인 쿼리가 니치 토픽을 밀어낼 수 있습니다. 각 쿼리는 최소 2개의 고유 결과를 보장받고, 나머지 슬롯은 스코어 순으로 채웁니다.

### CRAG 루프

모든 검색이 성공하는 건 아닙니다. Validator가 패시지 충분성을 체크하고, 최대 2회 쿼리 재작성을 트리거할 수 있어 파이프라인이 자기 교정합니다.

---

## 설정

| 설정 | 설명 |
|------|------|
| `rag_data_path` | `chunks.json`, `embeddings.npz`, `bm25_corpus.json`이 있는 디렉토리의 절대 경로 |
| `openai_api_key` | `text-embedding-3-small` 쿼리 임베딩용 OpenAI API 키 |

---

## 라이선스

MIT
