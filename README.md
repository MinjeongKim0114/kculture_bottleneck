# Cognitive-Behavioral Gap Analysis Service

## 프로젝트 목적

한국/한류에 대한 해외의 관심과 실제 방한·관광·소비 행동 사이의 "인지-행동 Gap(Cognitive-Behavioral Gap)"을 데이터로 측정하고, 다음을 제공하는 생성형 AI 대화형 서비스를 만든다.

1. 어느 국가/세그먼트에서 Gap이 큰지 발견
2. 왜 Gap이 발생하는지 정성 데이터와 보고서로 탐색
3. 생성형 AI가 근거와 함께 원인을 설명
4. 비즈니스 Opportunity를 제안

### MVP 대상 세그먼트

- 미방문 한류/한국 관심층
- 방한 관광객

### 향후 확장

- 국내 거주 외국인

## 기술 스택

| 영역 | 기술 |
|---|---|
| Frontend | Next.js, React, TypeScript |
| Backend | Python, FastAPI |
| Data Analysis | Python, pandas, NumPy |
| Database | PostgreSQL, pgvector |
| Data Pipeline | n8n |
| AI | Embedding, RAG, LLM API |
| Version Control | Git, GitHub |

## 프로젝트 구조

현재까지 확정된 폴더 구조는 다음과 같다. (아직 기능은 구현되지 않았다.)

```
project-root/
├── frontend/
│   ├── app/
│   ├── components/
│   ├── lib/
│   └── types/
│
├── backend/
│   └── app/
│       ├── api/
│       ├── services/
│       ├── rag/
│       └── models/
│
├── data/
│   ├── raw/
│   ├── processed/
│   └── notebooks/
│
├── workflows/
│   └── n8n/
│
└── docs/
```

## 현재 상태

[완료] 프로젝트 구조 / 개발 원칙(AGENTS.md)
[완료] 원본 데이터 확보 — 2026 해외한류실태조사 통계편 PDF(1,866페이지)
[완료] PDF 구조 분석 — 국가×표×페이지 매핑 (`data/processed/country_table_page_map.csv/json`)
[완료] 핵심 4개 표(1-16 호감도, 1-33 관심도, 1-35 인식변화, 1-41 관광경험) 30개국 전체 원수치 추출
       — 총 810개 값 중 809개 자동 추출, 1개(필리핀 1-16 패션)는 OCR 소수점 누락 의심으로 manual_review 상태 보존
[대기] 나머지 9개 표(1-3, 1-4, 1-15, 1-17, 1-18, 1-24, 1-26, 1-31, 1-37) 추출
[대기] 2025 잠재방한여행객조사 데이터 결합 (파일만 확보, 아직 분석 안 함)
[대기] Gap 계산 / 국가 비교·순위 / 지표 통합
[대기] 데이터베이스, API, 프론트엔드

추출 파이프라인 코드와 실행 방법은 `data/scripts/README.md` 참고.
