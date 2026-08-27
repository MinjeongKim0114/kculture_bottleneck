# 1. 프로젝트 소개

**외국인 방한 수요-장벽 갭 기반 사업 기회 발굴 서비스**는 해외 23개국의 한류/한국 문화 경험·호감도와 실제 방한 의향·행동 사이에 존재하는 "인지-행동 Gap"을 데이터로 측정하고, 그 Gap이 어떤 장벽 때문에 발생하는지 탐색해 신사업 기회로 연결하는 대시보드 + AI 챗봇 서비스입니다.

원본 데이터는 2026년 해외한류실태조사 통계 PDF(1,866페이지)이며, 이 안에 흩어진 국가별 원수치를 OCR로 추출·검증해 분석 가능한 형태로 만들었습니다.

## 서비스 이용하기

현재 로컬 개발 환경에서 실행 가능한 단계이며, 아직 외부 배포 URL은 없습니다. 실행 방법은 [11. 실행 방법](#11-실행-방법)을 참고하세요.

## 화면 예시

### [Overview 화면 — 세계지도 기반 23개국 탐색]

![Overview 화면](image.png)

### [Country Detail Panel — 국가 클릭 시 상세 패널]

![Country Detail Panel 화면](image.png)

### [AI 챗봇 — 멀티턴 대화 + 추천 후속 질문]

![AI 챗봇 화면](image.png)

---

# 2. 문제 정의

## 해결하고 싶은 문제

한류 콘텐츠에 대한 관심과 호감도는 국가마다 다르지만, "관심은 있는데 실제 방문으로 이어지지 않는" 격차가 왜, 어느 국가에서 크게 나타나는지 파악하기 어렵습니다.

특히 다음과 같은 문제가 있습니다.

- 원본 통계가 1,866페이지 PDF에 표 단위로 흩어져 있어 국가 간 비교가 사실상 불가능하다.
- Direct Gap(문화경험 대비 방문의향)과 Conditional Gap(문화경험자 중 방문의향), 그리고 8개 장벽(비자, 언어, 이미지, 비용 등)이 서로 다른 표에 흩어져 있어 "무엇 때문에 이 Gap이 생기는지" 종합적으로 보기 어렵다.
- 소표본 국가(응답자 30명 미만)를 다른 국가와 똑같이 취급하면 잘못된 결론으로 이어질 위험이 있다.
- 정량 데이터를 스스로 조회하며 질문하고 싶어도, 매번 원본 표를 다시 찾아야 한다.

## 대상 사용자

- 한류/방한 관광 마케팅 담당자
- 국가별 관광 정책을 기획하는 실무자
- 한류 확산 패턴을 공부하는 학생·분석가

## 기대 효과

사용자는 23개국의 Gap 크기와 장벽 패턴을 지도/표로 한눈에 비교하고, 궁금한 점을 챗봇에게 자연어로 물어 근거 데이터와 함께 답을 받을 수 있습니다.

---

# 3. MVP 범위

## 핵심 기능 3개

1. Overview 대시보드 (세계지도 기반 23개국 탐색 → 국가 클릭 시 상세 패널)
2. Supabase(PostgreSQL) 기반 정량 데이터 API (FastAPI)
3. 정량 데이터 기반 AI 챗봇 (`POST /api/chat` + Next.js 채팅 UI) — RAG 없이, DB에 실제로 있는 값만 근거로 답변하고, 같은 대화창 안에서는 이전 turn을 기억함

## 이번 MVP에서 제외한 기능

- **Gap Explorer / Barrier Explorer / Comparison 화면** — 백엔드 API(`GET /api/gaps`, `/api/barriers`, `/api/comparison`)는 이미 구현되어 있지만, 이를 소비하는 프론트엔드 화면은 아직 없습니다. 현재 프론트엔드는 Overview(세계지도 + 국가 상세 패널)와 AI 챗봇 두 화면만 존재합니다.
- 로그인/인증
- 성별/연령별/거주국별 세그먼트 집계 분석 (원본 세그먼트 데이터는 적재됐으나 집계/대시보드는 없음)
- 대화 기록의 서버 측 영구 저장 (현재는 브라우저 `localStorage`에만 저장 — 기기/브라우저를 바꾸면 안 보임)

## MVP 원칙

`data/processed/dashboard_data_dictionary.md`에 정의되지 않은 지표는 화면에도, 챗봇 응답에도 노출하지 않습니다. 데이터가 없는 질문에는 "지어내지 않고" 없다고 답하는 것을 정확성보다 우선했습니다.

---

# 4. 사용자 흐름 (usecase)

**대시보드 (구현된 흐름)**

```
접속 → Overview(세계지도, 지표 토글로 23개국 한눈에 보기)
     → 국가 클릭/호버 → Country Detail Panel
       (문화경험률/호감도/방한의향/Direct·Conditional Gap/주요 장벽 Top3/병목 프로파일 플래그)
```

Gap Explorer(Direct/Conditional Gap 축 비교), Barrier Explorer(8개 장벽 heatmap), Comparison(2~3개국 나란히 비교)은 백엔드 API까지만 구현되어 있고 프론트엔드 화면은 아직 없습니다 — 5장 참고.

**AI 챗봇**

```
/chat 페이지에서 자연어 질문 (+ 같은 대화창의 이전 turn 기록)
           → POST /api/chat
           → Supabase의 정량 데이터를 컨텍스트로 주입
           → OpenAI gpt-5.6-terra가 데이터 안에서만 답변 + 후속 질문 생성
           → 근거 있는 답변 + 추천 질문 반환 (없는 데이터는 "답변할 수 없다"고 응답)
           → 대화는 브라우저에 저장되어 사이드바에서 다시 열람 가능
```

---

# 5. 주요 기능

## 5.1 Overview *(구현됨)*

세계지도에서 23개국을 지표(문화경험률/방한의향 등) 토글로 색상 비교하며 한눈에 보고, 국가를 클릭하거나 호버하면 오른쪽에 상세 패널이 열립니다.

## 5.2 Country Detail Panel *(구현됨)*

선택한 국가의 문화경험률, 한류 호감도, 방한의향, Direct Gap, Conditional Gap(각각 tercile 배지 포함), 주요 장벽 Top3(방문 비의향자 기준), 병목 프로파일 플래그(5개 장벽 그룹 중 해당 여부)와 관찰 패턴 텍스트를 보여줍니다. 계산 기준·해석 주의사항은 접을 수 있는 섹션으로 따로 제공합니다.

## 5.3 Gap Explorer *(백엔드 API만 구현 — 프론트 화면 없음)*

`GET /api/gaps`가 Direct Gap과 Conditional Gap을 서로 다른 축으로 분리해 반환하고, 두 Gap 사이의 상관관계 데이터도 함께 제공합니다. 이를 시각화하는 프론트엔드 화면은 아직 없습니다.

## 5.4 Barrier Explorer *(백엔드 API만 구현 — 프론트 화면 없음)*

`GET /api/barriers`가 23개국 x 8개 장벽(한류 관심 부재, 낮은 한국 인지도, 부정적 한국 이미지, 불편한 언어소통, 여행경비/물가, 비자/출입국 절차, 장거리 비행, 불편한 종교환경) 데이터를 5개 그룹(인지/관심, 이미지, 경제/물리적 접근성, 제도/언어, 종교/문화환경)으로 묶어 반환합니다. heatmap 화면은 아직 없습니다.

## 5.5 Comparison *(백엔드 API만 구현 — 프론트 화면 없음)*

`GET /api/comparison?countries=...`으로 2~3개국의 프로파일을 함께 조회할 수 있습니다. 나란히 비교하는 화면은 아직 없습니다.

## 5.6 AI 챗봇

`/chat` 페이지(Next.js)에서 자연어로 질문하면 `POST /api/chat`이 Supabase에 있는 정량 데이터만 근거로 답변합니다. 아래와 같은 정확성 가드레일을 프롬프트에 내장했습니다.

- 데이터에 없는 수치·국가는 지어내지 않고 "답변할 수 없다"고 말한다 (이번 메시지에 실제로 첨부된 데이터 블록만 근거로 삼고, 이전 turn이나 규칙 설명에만 등장한 데이터 종류는 이번에 없으면 없는 것으로 취급 — [12.9](#129-대화-히스토리-도입-후-없는-데이터-종류를-형식만-보고-지어내는-문제) 참고)
- 상대적 위치(상위/중위/하위 3분위)는 미리 계산된 `country_pattern_profile`의 tier 값만 인용하고, LLM이 직접 평균과 비교 계산하지 않는다
- 소표본 국가는 표본 수와 함께 주의를 언급한다
- 상관관계(r/p)를 "원인"·"영향"으로 재서술하지 않는다
- 장벽/유형을 언급할 때 해당 국가의 플래그를 빠짐없이 확인한다
- JSON 키·테이블명뿐 아니라 데이터 값 안에 섞인 설문 문항 코드(예: `E1A-1`)도 노출하지 않는다 — 이런 코드는 애초에 프롬프트에 넣기 전에 서버에서 제거함 ([12.11](#1211-값-안에-내장된-내부-코드가-그대로-노출된-문제) 참고)

**대화 UI 기능**

- **같은 대화창 내 멀티턴 기억**: 프론트가 지금까지의 대화(질문/답변)를 매 요청마다 함께 보내고, 백엔드가 이를 이어붙여 모델에 전달합니다. 모델 자체가 학습되는 것이 아니라, 매 요청마다 대화 기록을 텍스트로 다시 첨부하는 방식입니다. 새 대화창을 열면 히스토리가 비어 시작되므로 대화창 간 기억은 없습니다.
- **대화 목록 저장/재열람**: 대화들을 브라우저 `localStorage`에 저장해, 새로고침해도 유지되고 사이드바에서 다시 열어볼 수 있습니다. 서버에는 저장하지 않으므로 다른 기기/브라우저에서는 보이지 않습니다.
- **추천 후속 질문**: 한 번의 API 호출에서 답변과 함께 최대 3개의 후속 질문을 구조화된 JSON(`response_format: json_object`)으로 함께 받아, 가장 최근 답변 아래에 클릭 가능한 칩으로 보여줍니다.
- **가독성 포맷팅**: 긴 답변은 모델이 `## 소제목` / `### 소소제목` 마커로 구조화하고, 프론트가 이를 크기·굵기로 계층화해 렌더링합니다.

---

# 6. 기술 스택

## Frontend

- Next.js
- React
- TypeScript

## Backend / Data Analysis

- Python
- FastAPI
- pandas, NumPy

## Database

- PostgreSQL (Supabase)

## AI

- OpenAI API (gpt-5.6-terra) — 정량 데이터 기반 챗봇 응답 생성
- pgvector — Reddit 정성 데이터(942건) 임베딩 검색 (text-embedding-3-small). 질문마다
  의미적으로 가까운 사례를 top-K로 찾아 챗봇 컨텍스트에 주입 (2026-08-26 추가)

## Automation / ETL

- **n8n** (self-hosted, Docker) — Reddit 정성 데이터 파이프라인(수집 → 전처리 → AI 사업테마 분류 → Supabase 적재 → 임베딩 생성)을 매주 자동 실행. n8n 컨테이너는 Python이 아예 없는 hardened 이미지라 파이프라인 스크립트를 직접 실행할 수 없어서, FastAPI의 `POST /internal/reddit-pipeline`(토큰 인증)을 호출해 서브프로세스로 실행하고 결과 요약만 돌려받는 구조입니다. 검토가 애매한("애매" 판정) 항목이 있으면 Gmail로 알림 메일을 보냅니다. (2026-08-26 구축, 동작 검증 완료)

---

# 7. 서비스 아키텍처

```
[원본 PDF, 1,866p]
       │  pymupdf 렌더링 + EasyOCR + 라벨 타겟 추출 (data/scripts/)
       ▼
[검증된 CSV, data/processed/]
       │  Table Editor CSV Import
       ▼
[Supabase (PostgreSQL), 15개 테이블]
       │  psycopg
       ▼
[FastAPI, DataRepository 추상화]
   ├─ GET /api/overview, /api/countries, /api/gaps, /api/barriers, /api/comparison
   │       │
   │       ▼
   │  [Next.js 프론트엔드 대시보드]
   │
   ├─ POST /api/chat  (history 포함, follow_up_questions 함께 응답)
   │       │  정량 데이터를 컨텍스트로 주입
   │       ▼
   │  [OpenAI gpt-5.6-terra]  ──▶  [Next.js /chat 채팅 UI, localStorage에 대화 저장]
   │
   └─ POST /internal/reddit-pipeline  (X-Internal-Token 인증)
           │  5개 파이프라인 스크립트를 서브프로세스로 순차 실행
           ▼
      [수집 → 전처리 → 사업테마 분류 → Supabase 적재 → 임베딩 생성]
           ▲
           │  Schedule Trigger(매주) → HTTP Request → IF(애매 판정 있음) → Send Email
      [n8n, self-hosted Docker]
```

`DataRepository`는 추상 인터페이스로 정의되어 있어(`backend/app/data_access/repository.py`), CSV 기반 구현(`CsvDataRepository`)과 PostgreSQL 기반 구현(`PostgresDataRepository`)을 서비스/API 계층 변경 없이 교체할 수 있습니다.

---

# 8. ERD 예시

`country`(23개국 고정 목록)를 기준으로 한 구조입니다. 전체 스키마는 [`backend/db/schema.sql`](backend/db/schema.sql) 참고.

```
country_profile_base (PK: country)  ──┬── gap_analysis (PK/FK: country)
                                       ├── conditional_gap_analysis (PK/FK: country)
                                       ├── barrier_pattern_analysis (PK/FK: country)
                                       ├── country_bottleneck_profile (PK/FK: country)
                                       ├── country_pattern_profile (PK/FK: country)
                                       └── country_bottleneck_observations (FK: country, 1:N)

독립 참조 테이블:
  bottleneck_type_summary (PK: type_code)
  gap_barrier_correlation (PK: pair, subset)
  sensitivity_analysis (PK: pair)
  country_indicator_distribution (PK: indicator)

원천 롱포맷 (모든 상위 표의 계산 원천):
  analysis_long (surrogate PK)

국가 범위가 다른 독립 테이블 (23개국 고정 목록과 조인 시 국가 목록 불일치 주의):
  content_liking_disliking_reasons (한류실태조사 30개국)
  potential_tourist_2025_survey (2025 잠재방한여행객조사 26개국, 세그먼트 롱포맷)
  reddit_qualitative_evidence (국가 무관, private DB — public 레포에는 원본 미포함)
```

---

# 9. API 명세 (핵심 명세만)

### 9.1 헬스체크

```
GET /api/health
```

### 9.2 Overview

```
GET /api/overview
```

응답 예시:

```json
{
  "indicator_distribution": [ { "indicator": "culture_experience_rate_pct", "mean": 80.63, "median": 86.33, "...": "..." } ],
  "country_grid": [ { "country": "미국", "culture_experience_rate_pct": 68.69, "visit_intention_positive_pct": 15.1, "observed_gap_pct_point": 53.59 } ],
  "bottleneck_type_summary": [ "..." ],
  "country_bottleneck_profiles": [ "..." ],
  "direct_gap": [ "..." ],
  "conditional_gap": [ "..." ]
}
```

### 9.3 국가 목록 / 상세

```
GET /api/countries
GET /api/countries/{country}
```

### 9.4 Gap Explorer *(API만 존재, 프론트 화면 미구현)*

```
GET /api/gaps
```

### 9.5 Barrier Explorer *(API만 존재, 프론트 화면 미구현)*

```
GET /api/barriers
```

### 9.6 Comparison *(API만 존재, 프론트 화면 미구현)*

```
GET /api/comparison?countries=러시아&countries=일본
```

### 9.7 AI 챗봇

```
POST /api/chat
Content-Type: application/json

{
  "question": "미국인들이 한국을 방문하지 않는 주된 이유는?",
  "history": [
    { "role": "user", "content": "미국의 Direct Gap은 어느 정도야?" },
    { "role": "assistant", "content": "미국의 Direct Gap은 53.59%p로 ..." }
  ]
}
```

`history`는 같은 대화창 내 이전 turn들(질문/답변)만 담습니다. 새 대화창을 시작하면 프론트가 빈 배열로 보내므로, 대화창 간 기억은 유지되지 않습니다.

응답 예시:

```json
{
  "answer": "미국의 Direct Gap은 53.59%p로 상위 3분위에 속하며, 주요 장벽은 ... 입니다.",
  "follow_up_questions": [
    "미국의 8개 장벽 중 가장 개선 여지가 큰 항목은?",
    "미국과 비슷한 Gap 패턴을 보이는 다른 국가가 있어?"
  ]
}
```

`follow_up_questions`는 최대 3개까지이며, 자연스러운 후속 질문이 없으면 빈 배열일 수 있습니다.

### 9.8 내부 파이프라인 트리거 (n8n 전용)

```
POST /internal/reddit-pipeline
X-Internal-Token: <backend/.env의 INTERNAL_PIPELINE_TOKEN>
```

Reddit 정성 데이터 수집~임베딩 5단계 스크립트를 순서대로 실행합니다. 외부에서 함부로 못 부르도록 토큰으로 게이트되어 있으며, n8n(Docker)의 Schedule Trigger가 매주 이 엔드포인트를 호출합니다.

응답 예시:

```json
{
  "status": "ok",
  "new_total": 12,
  "ambiguous_count": 2,
  "ambiguous": [ "..." ],
  "logs": { "collect_reddit_qualitative.py": { "returncode": 0, "...": "..." } }
}
```

`ambiguous_count`가 0보다 크면 n8n 워크플로가 Gmail로 검토 알림 메일을 보냅니다.

---

# 10. AI 코딩 에이전트 활용 방식

이 프로젝트는 AI 코딩 에이전트를 코드 생성기가 아니라, 데이터 정합성을 함께 검증하는 개발 파트너로 사용했습니다.

### 나쁜 요청 예시

```
Supabase sql 생성 코드 짜줘
```

### 좋은 요청 예시

```
dashboard_data_dictionary.md에 정의된 12개 표를 그대로 Supabase 테이블로 옮기고 싶어.
실제 CSV 컬럼/타입을 먼저 확인하고, 값이 실제로 일치하는지 검증한 다음 SQL을 짜줘.
```

### 프로젝트에서 사용한 작업 흐름

```
데이터 딕셔너리로 스키마 확정
→ 실제 CSV 값과 대조 검증
→ 구현 (DB 연동 / API / 챗봇)
→ 실제 호출로 검증 (curl → DB 원본 값과 대조)
→ 문제 발견 시 프롬프트/코드 수정 → 같은 질문으로 회귀 테스트
→ README 정리
```

특히 챗봇 품질 검증 단계에서는 "답변이 그럴듯한가"가 아니라 **"DB 원본 값과 숫자가 정확히 일치하는가"**를 매번 코드로 대조하는 방식을 사용했습니다. 이 과정에서 LLM이 스스로 계산한 비교값이 틀리는 것을 실제로 발견했고([12.3](#123-llm이-직접-계산한-비교값이-틀린-문제) 참고), 이후 "계산은 DB에서, LLM은 인용만" 원칙으로 프롬프트를 수정했습니다.

---

# 11. 실행 방법

## Backend

```bash
cd backend
pip install -r requirements.txt
# backend/.env 에 DATABASE_URL(Supabase 연결 문자열), LLM_API_KEY(OpenAI API 키) 설정
# INTERNAL_PIPELINE_TOKEN은 n8n Reddit 파이프라인(POST /internal/reddit-pipeline)을
# 쓸 때만 필요 — n8n 없이 대시보드/챗봇만 쓸 거면 생략 가능
uvicorn app.main:app --reload
```

## Frontend

```bash
cd frontend
npm install
# frontend/.env.local 에 NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000 설정
npm run dev
```

## n8n (선택 — Reddit 파이프라인 주간 자동화용)

대시보드/챗봇 실행에는 필요 없습니다. self-hosted Docker로 n8n을 띄우고, Schedule Trigger → HTTP Request(`POST http://host.docker.internal:8000/internal/reddit-pipeline`, `X-Internal-Token` 헤더) → IF(`ambiguous_count > 0`) → Send Email 순서로 워크플로를 구성하면 됩니다.

---

# 12. 트러블슈팅 기록

## 12.1 Supabase Direct Connection이 안 되는 문제

#### 현상

`.env`에 Supabase Direct Connection 문자열(`db.xxxxx.supabase.co`)을 넣었는데 `getaddrinfo failed` 에러로 연결이 안 됐습니다.

#### 원인

Direct Connection 호스트는 IPv6 주소(AAAA 레코드)만 제공하는데, 로컬 네트워크가 IPv6를 지원하지 않았습니다.

#### 해결

Supabase Connect 모달에서 IPv4로 접속 가능한 **Session Pooler** 연결 문자열(`aws-0-<region>.pooler.supabase.com`)로 교체했습니다.

## 12.2 CSV 임포트 시 정수 컬럼 타입 에러

#### 현상

`barrier_pattern_analysis`, `analysis_long`의 `sample_n` 컬럼을 Import할 때 `invalid input syntax for type integer: "73.0"` 에러가 발생했습니다.

#### 원인

CSV의 `sample_n`은 결측치(NaN) 때문에 pandas가 float으로 저장해 `73.0`처럼 소수점이 붙었는데, 스키마 컬럼 타입이 `integer`라 소수점 문자열을 정수로 캐스팅하지 못했습니다.

#### 해결

`sample_n` 컬럼 타입을 `double precision`으로 변경했습니다.

## 12.3 LLM이 직접 계산한 비교값이 틀린 문제

#### 현상

챗봇에게 "미국인들은 왜 한국을 안 가?"라고 물었더니, 미국의 문화경험률(68.69%)을 23개국 평균(80.63%)과 비교하면서 "평균보다 약간 높음"이라고 **잘못** 답했습니다(실제로는 평균보다 낮음).

#### 원인

프롬프트가 "23개국 평균과 비교해서 설명하라"고 지시했는데, 이건 LLM이 직접 두 숫자를 비교·판단하는 계산을 시키는 것이었습니다. 이 프로젝트의 원칙(정량 계산은 Python/PostgreSQL에서, LLM은 계산하지 않는다)에 어긋나는 지시였고, 실제로 계산이 틀렸습니다.

#### 해결

`country_pattern_profile` 테이블에 이미 계산되어 있는 tercile(`_tier`) 컬럼을 그대로 인용하도록 프롬프트를 바꿨습니다 — LLM은 계산하지 않고 사전 계산된 값만 인용합니다. 이후 재테스트에서 DB의 tier 값과 정확히 일치하는 답변을 확인했습니다.

## 12.4 백그라운드 작업 오케스트레이션 중 프로세스 중복 실행

#### 현상

PDF 표 추출 작업을 여러 백그라운드 에이전트에게 순서대로 이어받게 하는 과정에서, 같은 추출 스크립트가 동시에 최대 3개까지 중복 실행되어 같은 출력 파일에 겹쳐 쓸 뻔했습니다.

#### 원인

에이전트 세션이 끝나도 그 세션이 시작한 OS 프로세스는 계속 살아있는데, 이걸 고려하지 않고 다음 에이전트에게 같은 작업을 다시 시작하도록 지시했습니다.

#### 해결

발견 즉시 중복 프로세스를 모두 종료하고, 하나의 프로세스만 남긴 것을 확인한 뒤 진행했습니다. 스크립트가 모든 국가 처리를 끝낸 뒤에만 결과 파일을 쓰는 구조였기 때문에 중간 데이터 손실은 없었습니다.

## 12.5 AI 라벨링(population_type/business_theme) 오류 — 표본 검증으로 발견

#### 현상

Reddit 정성 데이터에 AI(gpt-4o-mini)가 1차로 붙인 population_type(잠재방문객/체류거주외국인 등)을 16건 표본으로 직접 대조했더니, 4건(25%)이 잘못 분류돼 있었습니다.

#### 원인

두 가지 패턴이 반복됐습니다. (1) "이미 여행했거나 살고 있는 분들께 묻습니다" 같은 문장에서, AI가 화자 본인의 상태가 아니라 글 속에 언급된 제3자(답변해줄 대상)를 화자 상태로 착각. (2) 과거 회고담이나 한국이 배경으로만 스친 글에도 business_theme을 붙임.

#### 해결

분류 프롬프트에 "화자 본인 vs 글 속 제3자 구분", "과거 회고/한국이 배경일 뿐인 글은 테마 비움" 두 지시를 추가하고 942건 전체를 재분류했습니다. 검증했던 4건 중 2건은 정확히 고쳐졌지만, "화자 본인 상태가 애매한 짧은 글"은 재분류 후에도 일부 남아있어 — 이 문서(`business_opportunity_themes.md`)에 인용 시 주의 문구를 남겨뒀습니다. 100% 정확한 AI 라벨링은 기대하기 어렵고, 표본 검증 → 프롬프트 수정 → 재실행 → 재검증 루프가 실질적인 개선 수단이었습니다.

## 12.6 reasoning 모델(gpt-5.6 계열)로 전환 시 `temperature` 미지원

#### 현상

챗봇/분류 스크립트 모델을 gpt-4o(-mini)에서 gpt-5.6-terra로 바꾸자 `temperature=0` 파라미터에서 `BadRequestError`가 발생했습니다.

#### 원인

reasoning 모델은 Chat Completions API에서 `temperature`를 커스텀 값으로 지원하지 않고 기본값(1)만 허용합니다(OpenAI 공식 문서 기준, Responses API 사용을 권장하지만 Chat Completions도 계속 지원됨).

#### 해결

`temperature=0` 파라미터를 제거했습니다(`seed=42`는 그대로 지원됨). 결정성은 프롬프트 내 "계산은 인용만, 사전 계산된 값만 사용" 원칙(12.3 참고)과 seed에 의존하는 구조로 유지됩니다.

## 12.7 pgvector 유사도 검색에서 파라미터 타입 캐스팅 누락

#### 현상

`chat_service.py`에서 질문 임베딩으로 `ORDER BY embedding <=> %s LIMIT %s` 쿼리를 실행하니 `operator does not exist: vector <=> double precision[]` 에러가 발생했습니다.

#### 원인

`pgvector.psycopg.register_vector`는 컬럼에 저장(`UPDATE ... SET embedding = %s`)할 때는 대상 컬럼 타입을 알 수 있어 자동 변환되지만, `ORDER BY` 같은 위치에서 파라미터로 바로 비교할 때는 psycopg가 Python list를 어떤 타입으로 보낼지 추론하지 못합니다.

#### 해결

쿼리에서 `%s::vector`로 명시적으로 캐스팅했습니다. 이후 정상 동작을 확인했습니다.

## 12.8 종료했다고 생각한 개발 서버가 남아 옛날 코드를 계속 서빙한 문제

#### 현상

`chat_service.py`/`page.tsx`를 여러 번 고쳐서 재시작해도, 브라우저에서는 수정 전과 똑같은 버그(로딩 스피너가 다른 대화창까지 잠그는 문제)가 계속 재현됐습니다.

#### 원인

`npm run dev`를 띄우는 백그라운드 작업을 중지시켰는데, `npm`이 실제로 띄운 자식 Node 프로세스는 종료되지 않고 3000번 포트를 계속 점유하고 있었습니다. 그 상태로 새 서버를 다시 띄우니 포트가 이미 사용 중이라 3001번으로 밀려났고, 브라우저는 계속 옛날 프로세스(수정 전 코드)와 통신하고 있었습니다.

#### 해결

`netstat -ano`로 3000번 포트를 실제로 점유한 프로세스의 PID를 확인하고 `taskkill /F /PID`로 강제 종료한 뒤, `.next/cache`를 지우고 서버를 재기동했습니다. 백그라운드 작업을 "중지"시켰다는 것이 곧 그 작업이 띄운 모든 하위 프로세스의 종료를 보장하지 않는다는 것을 확인했습니다 — 코드를 고쳤는데도 반영이 안 되면, 먼저 실제로 요청을 받는 프로세스가 그 코드를 서빙하는 프로세스가 맞는지(포트 점유 확인)부터 의심해야 합니다.

## 12.9 대화 히스토리 도입 후 없는 데이터 종류를 형식만 보고 지어내는 문제

#### 현상

멀티턴 대화 기억 기능을 추가한 뒤, 한 국가에 대해 실제 "2025 잠재방한여행객조사" 데이터로 정상 답변한 turn을 거치고 나서 다른 국가를 물었더니, 그 조사가 이번 국가에는 실제로 첨부되지 않았는데도 같은 이름과 형식으로 그럴듯한 수치를 만들어 답했습니다.

#### 원인

시스템 프롬프트가 "[2025 잠재방한여행객조사]가 포함되어 있으면 이렇게 다루라"는 규칙으로 이 데이터 종류의 존재 자체를 모델에게 설명해두고 있었는데, 정작 "이번 메시지에 그 블록이 안 보이면 언급 자체를 하지 마라"는 명시적 금지는 없었습니다. 게다가 멀티턴 히스토리로 이전 turn의 진짜 예시가 프롬프트에 그대로 남아있어, 모델이 그 형식을 다른 국가에도 재현하려는 경향이 강해졌습니다. LLM이 실제로 재학습되는 것은 아니고, 같은 대화 안에서 이전 turn의 텍스트를 그대로 다시 보고 패턴을 모방한 것입니다.

#### 해결

"이런 데이터 블록들은 질문에 국가가 매칭될 때만 이번 메시지에 첨부되며, 이번 메시지에 보이지 않으면 그 자료 자체가 없는 것이다. 대화 앞부분에 그런 이름의 데이터가 등장했더라도 이번 국가에 다시 첨부되지 않았다면 재사용하거나 흉내 내지 마라"는 규칙을 명시적으로 추가했습니다.

## 12.10 국가별 데이터 행 수 상한(LIMIT)이 큰 국가의 데이터를 조용히 잘라버린 문제

#### 현상

위 12.9를 조사하는 과정에서, AI가 "지어냈다"고 자백한 항목 중 일부(도시별 방문 의향, 콘텐츠 이용 빈도 등)가 실제로는 해당 조사에 존재하는 항목이라는 것을 DB에서 직접 확인했습니다.

#### 원인

과거 컨텍스트 토큰 초과 장애(UAE 826행 + 다른 블록 246행 → 128k 토큰 한도 초과) 대응으로 `ORDER BY page LIMIT 300`을 걸어뒀는데, 이 상한은 주제(topic) 관련성이 아니라 페이지 순서 기준이라 국가마다 어떤 주제가 잘리는지가 달랐습니다. 응답 데이터가 831행인 국가는 뒷부분 페이지의 주제가 통째로 빠졌고, 프롬프트에는 "컨텍스트 크기 제한으로 일부 항목만 포함됨"이라고만 되어 있어 정확히 뭐가 빠졌는지는 모델도 알 수 없었습니다.

#### 해결

각 행을 JSON(`{"topic": ..., "segment": ..., ...}`)으로 직렬화하던 방식을 `topic|segment|sample_n|item|value` 파이프 구분 텍스트로 바꿔, 반복되는 키 이름만큼의 토큰을 줄였습니다. 그 결과 국가당 최대 840행 정도를 다 넣어도 토큰 한도에 안전한 여유가 생겨, 임의로 자르지 않고 전량을 포함하도록 바꿨습니다(여러 국가가 동시에 매칭되는 극단적 경우만 대비해 상한을 5000행으로 넉넉히 올려둠). 같은 정보량이라도 직렬화 형식에 따라 토큰 비용이 크게 달라질 수 있다는 것을 확인했습니다.

## 12.11 값 안에 내장된 내부 코드가 그대로 노출된 문제

#### 현상

시스템 프롬프트에 "JSON 키·테이블명·컬럼명을 답변에 노출하지 마라"는 규칙이 있었는데도, 답변에 `E1A-1`, `B5B-1` 같은 설문 문항 코드가 그대로 나타났습니다.

#### 원인

이 코드는 JSON 키가 아니라 `gap_barrier_correlation`/`sensitivity_analysis` 테이블의 `pair` 컬럼 **값** 자체에 `"Direct_Gap(E1A-1-B5B-1) vs 한류_관심_부재"`처럼 박혀 있었습니다. 기존 규칙은 키·테이블명만 겨냥하고 있어 값 안에 섞인 내부 식별자까지는 막지 못했습니다.

#### 해결

프롬프트에 값 안의 코드도 옮기지 말라는 규칙을 추가한 것과 별개로, 더 확실한 방어로 데이터를 프롬프트에 넣기 전에 정규식(`\([A-Za-z0-9-]+\)`)으로 코드 부분 자체를 제거했습니다 — 모델이 애초에 코드를 볼 수 없게 데이터 계층에서 원천 차단하는 편이, 프롬프트 지시에만 의존하는 것보다 확실했습니다.

## 12.12 n8n의 hardened Docker 이미지 안에서 Python 스크립트를 직접 실행할 수 없던 문제

#### 현상

Reddit 파이프라인(수집→분류→적재→임베딩)을 n8n의 Execute Command 노드나 Code 노드로 직접 실행하려 했으나 계속 실패했습니다.

#### 원인

self-hosted n8n을 Docker의 공식 "hardened" Alpine 이미지로 띄웠는데, 이 이미지에는 Python은 물론 패키지 매니저조차 없습니다. Code 노드의 "네이티브 Python" 태스크 러너 모드도 문서상 파일시스템/네트워크 접근이 막혀 있어 이 파이프라인엔 애초에 쓸 수 없는 옵션이었습니다.

#### 해결

n8n 컨테이너 안에서 직접 실행하는 대신, `backend/app/api/routes/internal.py`에 `POST /internal/reddit-pipeline` 엔드포인트를 새로 만들어 FastAPI(호스트에서 실행 중, Python 환경 완비)가 5개 스크립트를 서브프로세스로 실행하고 결과 요약만 HTTP 응답으로 돌려주게 했습니다. n8n은 Docker Desktop이 제공하는 `http://host.docker.internal:8000`으로 이 엔드포인트를 호출합니다. 외부 스케줄러(n8n)와 핵심 로직(파이프라인 실행)의 역할을 API 경계로 명확히 분리한 것이 실행 환경 제약을 우회하는 동시에 책임도 깔끔하게 나누는 결과가 됐습니다.

## 12.13 Windows 작업 스케줄러가 권한 거부로 아예 동작하지 않은 문제

#### 현상

n8n의 스케줄 호출이 성공하려면 백엔드(FastAPI)가 항상 떠 있어야 하는데, 컴퓨터 재부팅 시 자동 실행을 `schtasks`로 등록하려 하자 가장 단순한 작업조차 "Access is denied"로 거부됐습니다.

#### 원인

해당 컴퓨터의 그룹 정책(Group Policy) 설정으로 작업 스케줄러 등록 자체가 잠겨 있는 것으로 추정됩니다.

#### 해결

`schtasks` 대신 Windows 시작프로그램 폴더(`shell:startup`)에 `backend/start_backend.bat`를 가리키는 바로가기(.lnk)를 만들어, 로그인 시 최소화된 창으로 백엔드가 자동 실행되게 했습니다. 특정 환경에서 표준 자동화 도구가 정책으로 막혀 있으면, 우회로(시작프로그램 폴더 등)가 있는지부터 확인하는 게 낫다는 것을 확인했습니다.

## 12.14 Gmail SMTP 587번 포트에서 SSL 협상 에러

#### 현상

n8n의 Send Email 노드로 Gmail(587번 포트, 앱 비밀번호 인증)에 연결하니 `SSL routines:tls_validate_record_header:wrong version number` 에러가 발생했습니다.

#### 원인

n8n의 SMTP 자격증명 설정에는 "SSL/TLS"와 "Disable STARTTLS"라는 별개의 토글이 있는데, 587번 포트는 STARTTLS로 스스로 암호화 연결을 협상하는 방식이라 "SSL/TLS" 토글을 켜면 안 됩니다. 이 둘을 혼동해 SSL/TLS를 켠 채로 587번 포트에 접속을 시도했습니다.

#### 해결

두 토글을 모두 꺼서(SSL/TLS 끄기, STARTTLS는 비활성화하지 않기) 587번 포트 기본 동작에 맞췄습니다. 이후 전체 워크플로(Schedule Trigger → HTTP Request → IF → Send Email)가 정상 동작해 실제 Gmail 수신함으로 알림 메일이 도착하는 것까지 확인했습니다.

---

# 13. 회고

### 잘 된 점

- 데이터 딕셔너리를 먼저 확정하고 그 기준으로만 스키마/챗봇 컨텍스트를 만들어서, 존재하지 않는 지표가 화면이나 챗봇 답변에 섞여 들어가는 일을 막을 수 있었습니다.
- 챗봇을 "그럴듯한 답변"이 아니라 "DB 원본 값과 숫자가 일치하는가"로 검증하는 습관 덕분에, LLM이 스스로 계산하다 틀리는 문제를 실제로 잡아낼 수 있었습니다.
- 정량 계산은 DB/Python에서, LLM은 서술·인용만 한다는 원칙을 코드(프롬프트)로 구체화했습니다.

### 어려웠던 점

- Supabase Direct Connection의 IPv6 이슈처럼 로컬 네트워크 환경에 따라 달라지는 문제는 원인을 찾는 데 시간이 걸렸습니다.
- 프롬프트로 지시해도 LLM이 100% 지키지 않는 경우(장벽 완전성 누락, 없는 비교값 생성)가 있어, 프롬프트만으로는 정확성을 완전히 보장할 수 없다는 한계를 확인했습니다.
- 여러 백그라운드 작업을 순서대로 이어받게 하는 과정에서 프로세스 중복 실행 사고가 있었습니다 — 비동기 작업 상태 추적의 중요성을 체감했습니다.
- 멀티턴 대화 기억을 추가하자 새로운 종류의 문제가 따라왔습니다 — 이전 turn의 진짜 답변이 프롬프트에 그대로 남아있으니, 모델이 그 형식을 다른 국가/다른 turn에도 억지로 재현하려는 경향이 생겼습니다([12.9](#129-대화-히스토리-도입-후-없는-데이터-종류를-형식만-보고-지어내는-문제)). 기능 하나(대화 기억)를 추가하면 그게 다른 안전장치(그라운딩 규칙)와 상호작용해 새 실패 유형을 만들 수 있다는 것을 체감했습니다.

### 배운 점

- LLM에게 "직접 비교/계산하라"고 시키는 프롬프트는 그 자체로 위험 신호이며, 계산은 가능한 한 사전에 코드로 끝내고 LLM에게는 인용만 맡겨야 합니다.
- `temperature=0`도 완전한 결정성을 보장하지 않는다는 것을 실제로 확인했습니다 — 일관성이 중요한 서비스라면 프롬프트 외에 후처리 검증 단계가 필요합니다.
- 같은 질문으로 프롬프트 변경 전/후를 비교하는 회귀 테스트가 "느낌"이 아니라 근거 있는 개선을 만듭니다.
- "데이터에 없으면 지어내지 마라"는 한 문장으로는 부족합니다. 할루시네이션은 (1) 완전히 없는 것을 창작, (2) 실제로 있는데 상한/절단 때문에 안 보여서 대신 지어냄, (3) 진짜 값 여러 개를 조합해 없는 새 숫자를 합성 — 적어도 세 가지 다른 경로로 생깁니다. 원인마다 대응이 다르므로("없다고 말해라" vs "자르지 말고 다 넣어라" vs "출력 후 검증"), 증상만 보고 프롬프트만 계속 손보기보다 실제 데이터 흐름을 추적해 원인부터 구분하는 것이 중요했습니다.
- 값 안에 섞인 내부 식별자(설문 문항 코드 등)는 "키/컬럼명 노출 금지" 규칙만으로는 안 걸러집니다. 노출을 막고 싶은 대상이 정확히 무엇인지(키 vs 값)를 구분해서, 가능하면 프롬프트 지시보다 데이터 계층에서 원천 차단하는 것이 더 확실합니다.

---

# 14. 향후 개선 방향

- **Gap Explorer / Barrier Explorer / Comparison 프론트엔드 화면 구현** — 백엔드/데이터 쪽은 비교적 안정화됐고, 이 3개 화면이 현재 가장 큰 미구현 조각입니다. 대응하는 API(`GET /api/gaps`, `/api/barriers`, `/api/comparison`)는 이미 있으므로 프론트엔드 작업만 남아있습니다.
- LLM 응답의 사실 일치 여부를 자동으로 확인하는 후처리 검증 단계 추가 — 답변에 나온 숫자를 정규식으로 추출해 이번 turn에 실제로 주입한 데이터 값과 대조하는 방식을 검토 중. 12.9/12.10에서 고친 것은 "없는 데이터를 언급하는" 유형과 "잘려서 안 보이는" 유형이고, 진짜 값 여러 개를 조합해 새 숫자를 합성하는 유형(예: 서로 다른 항목의 응답자 수/비율을 섞어 존재하지 않는 통계를 만들어냄)은 프롬프트 규칙만으로는 완전히 막지 못해 이 단계가 필요하다고 판단
- 대화 기록의 서버 측 저장 — 현재는 브라우저 `localStorage`뿐이라 기기를 바꾸면 안 보임. 로그인 붙기 전까지는 우선순위 낮음
- n8n 파이프라인 추가 개선 — 현재 상태로 동작 검증까지 끝났지만(6장 Automation/ETL
  참고), "신규 항목 없음" 하트비트 알림이나 Reddit 외 다른 수집 소스로의 확장은 아직
  다루지 않음
- 세그먼트별(성별/연령별/거주국별) 분석 — 2025 잠재방한여행객조사 데이터 자체는 이미
  결합·적재 완료됐고 챗봇이 개별 질문에 인용 가능하지만, 국가별 세그먼트 Gap을 비교하는
  집계 분석/대시보드는 아직 없음. 구체적인 비교 질문이 생기면 그때 착수 권장
