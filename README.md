# 1. 프로젝트 소개

**한류 인지-행동 Gap 분석 서비스(Cognitive-Behavioral Gap Analysis Service)**는 해외 23개국의 한류/한국 문화 경험·호감도와 실제 방한 의향·행동 사이에 존재하는 "인지-행동 Gap"을 데이터로 측정하고, 그 Gap이 어떤 장벽 때문에 발생하는지 탐색할 수 있는 대시보드 + AI 챗봇 서비스입니다.

원본 데이터는 2026년 해외한류실태조사 통계 PDF(1,866페이지)이며, 이 안에 흩어진 국가별 원수치를 OCR로 추출·검증해 분석 가능한 형태로 만들었습니다.

## 서비스 이용하기

현재 로컬 개발 환경에서 실행 가능한 단계이며, 아직 외부 배포 URL은 없습니다. 실행 방법은 [11. 실행 방법](#11-실행-방법)을 참고하세요.

## 화면 예시

### [Overview 화면 — 세계지도 기반 23개국 탐색]

![Overview 화면](image.png)

### [Country Explorer — 국가 클릭 시 상세 패널]

![Country Explorer 화면](image.png)

### [Gap / Barrier 요약 카드]

![Gap 요약 카드](image.png)

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

1. 23개국 Gap/장벽 대시보드 (Overview → Country Explorer → Gap/Barrier Explorer → Comparison)
2. Supabase(PostgreSQL) 기반 정량 데이터 API (FastAPI)
3. 정량 데이터 기반 AI 챗봇 (`POST /api/chat`) — RAG 없이, DB에 실제로 있는 값만 근거로 답변

## 이번 MVP에서 제외한 기능

- 로그인/인증
- 정성 데이터(Reddit 등) 기반 RAG, pgvector 임베딩 검색
- n8n ETL 자동화 파이프라인
- 연령/소득 등 세그먼트별 분석
- 프론트엔드 챗봇 UI (현재는 백엔드 API까지만 구현)

## MVP 원칙

`data/processed/dashboard_data_dictionary.md`에 정의되지 않은 지표는 화면에도, 챗봇 응답에도 노출하지 않습니다. 데이터가 없는 질문에는 "지어내지 않고" 없다고 답하는 것을 정확성보다 우선했습니다.

---

# 4. 사용자 흐름 (usecase)

**대시보드**

```
접속 → Overview(세계지도, 23개국 한눈에 보기)
     → 국가 클릭 → Country Detail Panel(문화경험률/호감도/방한의향/Direct·Conditional Gap/8개 장벽)
     → Gap Explorer / Barrier Explorer 에서 심화 탐색
     → 2~3개국 선택해 Comparison
```

**AI 챗봇 (백엔드 API)**

```
자연어 질문 → POST /api/chat
           → Supabase의 정량 데이터(23개국 x 10개 표)를 컨텍스트로 주입
           → GPT-4o가 데이터 안에서만 답변 생성
           → 근거 있는 답변 반환 (없는 데이터는 "답변할 수 없다"고 응답)
```

---

# 5. 주요 기능

## 5.1 Overview

세계지도에서 23개국을 한눈에 보고, 국가를 클릭하면 상세 패널이 열립니다. Direct/Conditional Gap 요약 카드와 병목 유형(Type A~G) 요약 카드를 함께 제공하며, 전체 국가를 표 형태로 펼쳐볼 수 있습니다.

## 5.2 Country Explorer

선택한 국가의 문화경험률, 한류 호감도, 방한의향, Direct Gap, Conditional Gap, 8개 장벽 중 상위 3개, tercile(상위/중위/하위 3분위) 위치, 병목 유형 플래그(Type A~G)를 함께 보여줍니다.

## 5.3 Gap Explorer

Direct Gap과 Conditional Gap을 서로 다른 축으로 분리해서 비교하고, 두 Gap 사이의 상관관계를 함께 제공합니다.

## 5.4 Barrier Explorer

23개국 x 8개 장벽(한류 관심 부재, 낮은 한국 인지도, 부정적 한국 이미지, 불편한 언어소통, 여행경비/물가, 비자/출입국 절차, 장거리 비행, 불편한 종교환경) heatmap을 5개 그룹(인지/관심, 이미지, 경제/물리적 접근성, 제도/언어, 종교/문화환경)으로 묶어 제공합니다.

## 5.5 Comparison

2~3개국을 선택해 Country Explorer 프로파일을 나란히 비교합니다.

## 5.6 AI 챗봇 (백엔드)

`POST /api/chat`으로 자연어 질문을 받아, Supabase에 있는 정량 데이터만 근거로 답변합니다. 아래와 같은 정확성 가드레일을 프롬프트에 내장했습니다.

- 데이터에 없는 수치·국가는 지어내지 않고 "답변할 수 없다"고 말한다
- 상대적 위치(상위/중위/하위 3분위)는 미리 계산된 `country_pattern_profile`의 tier 값만 인용하고, LLM이 직접 평균과 비교 계산하지 않는다
- 소표본 국가는 표본 수와 함께 주의를 언급한다
- 상관관계(r/p)를 "원인"·"영향"으로 재서술하지 않는다
- 장벽/유형을 언급할 때 해당 국가의 플래그를 빠짐없이 확인한다

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

- OpenAI API (GPT-4o) — 정량 데이터 기반 챗봇 응답 생성

## 계획되어 있으나 아직 미구현

- pgvector, RAG (정성 데이터 임베딩 검색)
- n8n (ETL 자동화)

---

# 7. 서비스 아키텍처

```
[원본 PDF, 1,866p]
       │  pymupdf 렌더링 + EasyOCR + 라벨 타겟 추출 (data/scripts/)
       ▼
[검증된 CSV, data/processed/]
       │  Table Editor CSV Import
       ▼
[Supabase (PostgreSQL), 12개 테이블]
       │  psycopg
       ▼
[FastAPI, DataRepository 추상화]
   ├─ GET /api/overview, /api/countries, /api/gaps, /api/barriers, /api/comparison
   │       │
   │       ▼
   │  [Next.js 프론트엔드 대시보드]
   │
   └─ POST /api/chat
           │  정량 데이터를 컨텍스트로 주입
           ▼
      [OpenAI GPT-4o]
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

### 9.4 Gap Explorer

```
GET /api/gaps
```

### 9.5 Barrier Explorer

```
GET /api/barriers
```

### 9.6 Comparison

```
GET /api/comparison?countries=러시아&countries=일본
```

### 9.7 AI 챗봇

```
POST /api/chat
Content-Type: application/json

{ "question": "미국인들이 한국을 방문하지 않는 주된 이유는?" }
```

응답 예시:

```json
{ "answer": "미국의 Direct Gap은 53.59%p로 상위 3분위에 속하며, 주요 장벽은 ... 입니다." }
```

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

특히 챗봇 품질 검증 단계에서는 "답변이 그럴듯한가"가 아니라 **"DB 원본 값과 숫자가 정확히 일치하는가"**를 매번 코드로 대조하는 방식을 사용했습니다. 이 과정에서 LLM이 스스로 계산한 비교값이 틀리는 것을 실제로 발견했고([12.4](#124-llm이-직접-계산한-비교값이-틀린-문제) 참고), 이후 "계산은 DB에서, LLM은 인용만" 원칙으로 프롬프트를 수정했습니다.

---

# 11. 실행 방법

## Backend

```bash
cd backend
pip install -r requirements.txt
# backend/.env 에 DATABASE_URL(Supabase 연결 문자열), LLM_API_KEY(OpenAI API 키) 설정
uvicorn app.main:app --reload
```

## Frontend

```bash
cd frontend
npm install
# frontend/.env.local 에 NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000 설정
npm run dev
```

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

## 12.3 `.env` 값에 공백이 섞여 들어간 문제

#### 현상

`DATABASE_URL= postgresql://...`처럼 `=` 뒤에 공백이 들어가 값 앞에 스페이스가 포함될 뻔했습니다.

#### 해결

`.env`는 `KEY=값` 형식을 그대로 쓰면 되고 따옴표는 필요 없다는 점을 확인하고, 공백을 제거했습니다.

## 12.4 LLM이 직접 계산한 비교값이 틀린 문제

#### 현상

챗봇에게 "미국인들은 왜 한국을 안 가?"라고 물었더니, 미국의 문화경험률(68.69%)을 23개국 평균(80.63%)과 비교하면서 "평균보다 약간 높음"이라고 **잘못** 답했습니다(실제로는 평균보다 낮음).

#### 원인

프롬프트가 "23개국 평균과 비교해서 설명하라"고 지시했는데, 이건 LLM이 직접 두 숫자를 비교·판단하는 계산을 시키는 것이었습니다. 이 프로젝트의 원칙(정량 계산은 Python/PostgreSQL에서, LLM은 계산하지 않는다)에 어긋나는 지시였고, 실제로 계산이 틀렸습니다.

#### 해결

`country_pattern_profile` 테이블에 이미 계산되어 있는 tercile(`_tier`) 컬럼을 그대로 인용하도록 프롬프트를 바꿨습니다 — LLM은 계산하지 않고 사전 계산된 값만 인용합니다. 이후 재테스트에서 DB의 tier 값과 정확히 일치하는 답변을 확인했습니다.

## 12.5 백그라운드 작업 오케스트레이션 중 프로세스 중복 실행

#### 현상

PDF 표 추출 작업을 여러 백그라운드 에이전트에게 순서대로 이어받게 하는 과정에서, 같은 추출 스크립트가 동시에 최대 3개까지 중복 실행되어 같은 출력 파일에 겹쳐 쓸 뻔했습니다.

#### 원인

에이전트 세션이 끝나도 그 세션이 시작한 OS 프로세스는 계속 살아있는데, 이걸 고려하지 않고 다음 에이전트에게 같은 작업을 다시 시작하도록 지시했습니다.

#### 해결

발견 즉시 중복 프로세스를 모두 종료하고, 하나의 프로세스만 남긴 것을 확인한 뒤 진행했습니다. 스크립트가 모든 국가 처리를 끝낸 뒤에만 결과 파일을 쓰는 구조였기 때문에 중간 데이터 손실은 없었습니다.

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

### 배운 점

- LLM에게 "직접 비교/계산하라"고 시키는 프롬프트는 그 자체로 위험 신호이며, 계산은 가능한 한 사전에 코드로 끝내고 LLM에게는 인용만 맡겨야 합니다.
- `temperature=0`도 완전한 결정성을 보장하지 않는다는 것을 실제로 확인했습니다 — 일관성이 중요한 서비스라면 프롬프트 외에 후처리 검증 단계가 필요합니다.
- 같은 질문으로 프롬프트 변경 전/후를 비교하는 회귀 테스트가 "느낌"이 아니라 근거 있는 개선을 만듭니다.

---

# 14. 향후 개선 방향

- Reddit 등 정성 데이터 크롤링 → RAG 파이프라인(pgvector) 구축 — 지금은 "무엇이 장벽인지"의 %만 있고 "왜 그런지"에 대한 정성적 근거가 없음
- 표 1-17(호감요인)/1-18(호감 저해요인)/1-37(한류 부정적 인식 공감 이유) 추출·반영 — "왜"를 설명하는 정량 데이터 보강 (진행 중)
- 프론트엔드 챗봇 UI 추가 (현재는 백엔드 API까지만 구현)
- LLM 응답의 사실 일치 여부를 자동으로 확인하는 후처리 검증 단계 추가
- n8n 기반 ETL 자동화
- 2025 잠재방한여행객조사 결합 및 세그먼트별(연령/소득 등) 분석
