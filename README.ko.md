<div align="center">

# fablers-agentic-rag

**문서에게 물어보세요. 출처가 달린 답변을 받으세요.**

쿼리 분석, 하이브리드 검색, 평가 및 CRAG 검증, 인용 답변 합성까지 — Claude 에이전트가 오케스트레이션하는 Agentic RAG 파이프라인 플러그인. PDF, 텍스트, 마크다운 지원.

[![Claude Code Plugin](https://img.shields.io/badge/Claude_Code-Plugin-blueviolet?style=for-the-badge)](https://claude.ai)
[![Version](https://img.shields.io/badge/version-2.0.1-blue?style=for-the-badge)](#)
[![License: MIT](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](LICENSE)

[English](README.md) | [한국어](README.ko.md) | [日本語](README.ja.md)

</div>

---

## 이게 뭔가요?

문서는 있고, 질문도 있는데 — 키워드 검색은 부정확하고 LLM은 출처 없이 환각합니다.

**fablers-agentic-rag**가 그 간극을 메웁니다: 문서(PDF, TXT, 마크다운)를 청킹하고, 벡터 + BM25로 인덱싱한 뒤, 3에이전트 파이프라인이 검색하고, 검증하고, 페이지 단위 인용이 달린 답변을 합성합니다 — Claude Code 안에서 전부.

---

## 왜 만들었나요?

Claude Code로 RAG를 하는 방법은 많습니다. Obsidian + MCP 서버 + 벡터 DB + 별도 AI를 연결하면 됩니다. 동작은 하는데 — 이제 도구 네 개를 각각 설치하고, 업데이트하고, 관리해야 합니다.

아니면 PDF 전체를 Claude에게 던질 수도 있습니다. 하지만 600페이지 책은 컨텍스트 윈도우를 넘기고, 들어간다 해도 질문할 때마다 전체를 다시 읽혀야 하니 토큰이 폭발합니다.

이 플러그인은 다른 접근을 택했습니다: **하나의 도구, 하나의 워크플로우**. 인덱싱, 검색, 검증, 답변 — 전부 Claude Code 안에서. OpenAI가 관여하는 유일한 이유는 Claude가 임베딩 API를 (아직) 제공하지 않기 때문입니다. 나머지 전부는 이미 쓰고 있는 Claude가 처리합니다.

### vs. 일반 RAG MCP

| | 일반 RAG MCP | 이 플러그인 |
|---|---|---|
| **워크플로우** | Obsidian / 벡터 DB / 외부 AI — 여러 도구 관리 | **Claude Code만** — 인덱싱부터 답변까지 한 곳에서 |
| **두뇌** | 외부 LLM API 호출 (OpenAI 등)로 추론 | **Claude Code 에이전트가 곧 두뇌** — 외부 LLM 불필요 |
| **아키텍처** | 검색 → 붙여넣기 | 멀티 에이전트 파이프라인 + 검증 |
| **품질 검증** | 없음 — 벡터 검색 결과를 그대로 반환 | CRAG 검증이 모든 패시지를 점수화, 부족하면 쿼리 재작성 후 재시도 |
| **복잡한 질문** | 모든 쿼리에 동일 경로 | 복잡도 라우팅 — 단순 1에이전트, 복합 3에이전트 |
| **인용** | 청크 덤프 또는 없음 | 모든 주장에 `[Source N]` 인라인 인용 + 출처 섹션 |
| **검색 방식** | 벡터 단독 (정확한 용어 누락) | 하이브리드 벡터 + BM25 (의미와 키워드 모두 포착) |
| **인프라** | 종종 Docker, 벡터 DB 서버 필요 | 인프라 제로 — Python 파일 + Claude 에이전트만 |
| **자기 교정** | 원샷, 재시도 없음 | CRAG 루프가 결과 부족 시 쿼리를 최대 2회 재작성 |

### vs. PDF 전체를 컨텍스트에 넣기

| | PDF 전체 넣기 | 이 플러그인 |
|---|---|---|
| **~50페이지** | 잘 동작. 그냥 읽혀라. | 오버킬 |
| **~150페이지 이상** | 컨텍스트 초과 또는 비용 폭발 | 인덱스 1회, 이후 저렴하게 질문 |
| **반복 질문** | 매번 전체 재전송 (10개 질문 = 10배 비용) | 1회 인덱싱, 질문당 ~5K 토큰 |
| **인용 정확도** | 페이지 번호 환각 가능 | 청크 메타데이터에 정확한 페이지/헤딩 |

유일한 외부 API 호출은 쿼리 임베딩용 OpenAI `text-embedding-3-small`뿐입니다. 그 외 전부 — 쿼리 분석, 리랭킹, 검증, 답변 합성 — Claude Code 자체 에이전트 시스템이 처리합니다. 추가 LLM 비용 없음.

**요약**: MCP는 검색 결과를 줍니다. 이 플러그인은 검증된, 인용이 달린 답변을 줍니다 — 어차피 결제한 Claude Code 토큰, 기분 좋게 써보세요.

### 소형 아크 원자로, 발전소가 아닙니다

이 플러그인은 실제 필요에서 탄생했습니다: Jesse Schell의 *The Art of Game Design* — 600페이지 분량의 게임 디자인 이론서에서 아이디에이션을 하기 위해. 목표는 수백만 건의 문서를 인덱싱하는 게 아니었습니다. 한 권을 깊이 이해하는 것이었습니다.

프로젝트에 떨어뜨리는 소형 자기 완결형 원자로라고 생각하세요:

- 인용 달린 답변으로 공부하고 싶은 교재
- 정확하게 참조해야 하는 기술 매뉴얼
- 교차 검증하고 싶은 논문
- 쿼리하고 싶은 프로젝트 문서

numpy 배열 + 인메모리 BM25 — 벡터 DB도, 서버도, Docker도 없습니다. 파일 몇 개 규모라면 이것만으로 충분합니다. 수백만 건의 엔터프라이즈급 지식 베이스에는 GraphRAG이나 전용 벡터 DB 솔루션을 사용하세요.

---

## v2.0.0 변경사항

- **더 빠르게**: 5개 → 3개 에이전트 — 단순 질문은 에이전트 1회 호출만
- **간결한 구조**: 리포 루트 = 플러그인 (중첩 `plugin/` 디렉토리 제거)
- **새 커맨드**: `/search` 직접 검색, `/ingest` 문서 인덱싱
- **스마트 라우팅**: 복잡도 기반 분기로 불필요한 에이전트 스킵

---

## 작동 방식

```
/ask 엘리멘탈 테트라드와 게임 메카닉스의 관계는?
```

**단순 질문** (에이전트 1회 호출):
```
You ── /ask ──▶ 스킬이 2개 쿼리 생성 ──▶ search.py ──▶ Answer Synthesizer
                                                          │
                                                    인용된 답변
                                                    [Source N] 포함
```

**복잡한 질문** (에이전트 최대 3회 호출):
```
You ── /ask ──▶ Query Analyst ──▶ search.py ──▶ Evaluator ──▶ Answer Synthesizer
                  │                                │                │
             2-5개 하위                       리랭킹 + CRAG       인용된 답변
             쿼리로 분해                      검증               [Source N] 포함
                                                   │
                                             ┌─────┴──────┐
                                             │  재시도?    │
                                             │  쿼리 재작성│──▶ search.py로 복귀
                                             │  (최대 2회) │
                                             └────────────┘
```

### 3개 에이전트

| # | 에이전트 | 역할 |
|---|---------|------|
| 1 | **Query Analyst** | 복합 질문을 2-5개 구체적 검색 쿼리로 분해. 단순 질문에서는 스킵. |
| 2 | **Evaluator** | 검색 결과 리랭킹 (상위 5개) + CRAG 검증. 쿼리 재작성 트리거 가능 (최대 2회). |
| 3 | **Answer Synthesizer** | 인라인 `[Source N]` 인용과 출처 섹션이 포함된 최종 답변 생성. |

---

## 빠른 시작

### 1. 플러그인 설치

Claude Code에서 마켓플레이스 추가 후 설치:
```
/plugin marketplace add flashwade03/fablers-rag
/plugin install fablers-agentic-rag@rag
```

### 2. 데이터 준비

의존성 설치 후 인제스션 파이프라인 실행:

```bash
pip install openai numpy rank_bm25 pdfplumber
cd scripts && python3 ingest.py --document /path/to/your/document.pdf --output-dir ../data
```

또는 플러그인 설치 후 `/ingest` 커맨드를 사용하세요.

`.pdf`, `.txt`, `.md` 파일을 지원합니다. `--skip-embeddings`로 청킹만 테스트할 수 있습니다.

### 3. 설정

첫 세션 시작 시 플러그인이 `.claude/fablers-agentic-rag.local.md`를 생성합니다. 편집:

```yaml
rag_data_path: /absolute/path/to/data
openai_api_key: sk-...
```

### 4. 질문하기

```
/ask 3장의 핵심 개념은 무엇인가?
/ask 저자가 정의한 주요 프레임워크는 무엇이고, 각 요소를 평가하는 도구는?
```

### 기타 커맨드

```
/search 게임 디자인이란?              # 직접 하이브리드 검색, 원시 결과
/ingest /path/to/new-document.pdf   # 새 문서 인덱싱
```

---

## 프로젝트 구조

```
fablers-rag/                          ← 리포 루트 = 플러그인
├── .claude-plugin/
│   ├── plugin.json                   # 플러그인 매니페스트 (v2.0.1)
│   └── marketplace.json              # 마켓플레이스 메타데이터
├── agents/
│   ├── query-analyst.md              # 쿼리 분해
│   ├── evaluator.md                  # 리랭킹 + CRAG 검증
│   └── answer-synthesizer.md         # 인용 답변 생성
├── commands/
│   ├── ask.md                        # /ask 커맨드
│   ├── search.md                     # /search 커맨드
│   └── ingest.md                     # /ingest 커맨드
├── skills/
│   └── ask/SKILL.md                  # 파이프라인 오케스트레이션
├── scripts/
│   ├── search.py                     # 하이브리드 검색 엔진
│   ├── ingest.py                     # 문서 인제스션 파이프라인
│   ├── chunker.py                    # 자동 감지 청킹 전략
│   ├── embedder.py                   # OpenAI 임베딩
│   ├── config.py                     # 청킹/임베딩 설정
│   └── session-start.sh              # 세션 초기화
├── hooks/
│   └── hooks.json                    # 이벤트 훅
├── fablers-rag.template.md           # 설정 템플릿
└── SKILL.md                          # 루트 스킬
```

---

## 핵심 설계 결정

### 하이브리드 검색 (Vector + BM25)

순수 벡터 검색은 정확한 용어를 놓칩니다. 순수 키워드 검색은 의미를 놓칩니다. 하이브리드 방식(alpha=0.6 벡터, 0.4 BM25)이 둘 다 잡습니다.

### 복잡도 기반 분기

단순 팩트 질문은 쿼리 분석과 평가를 건너뛰어 5회 에이전트 호출을 1회로 줄여 응답 속도를 개선합니다. 복합 다파트 질문은 전체 파이프라인을 사용합니다.

### CRAG 루프

모든 검색이 성공하는 건 아닙니다. Evaluator가 패시지 충분성을 체크하고, 최대 2회 쿼리 재작성을 트리거할 수 있어 파이프라인이 자기 교정합니다.

---

## 설정

| 설정 | 설명 |
|------|------|
| `rag_data_path` | `chunks.json`, `embeddings.npz`, `bm25_corpus.json`이 있는 디렉토리의 절대 경로 |
| `openai_api_key` | `text-embedding-3-small` 쿼리 임베딩용 OpenAI API 키 |

---

## 라이선스

MIT
