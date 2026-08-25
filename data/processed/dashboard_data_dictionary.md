# 대시보드/AI 데이터 딕셔너리

대시보드와 AI Analyst가 참조하는 모든 CSV의 컬럼을 정의한다. 여기 없는 필드는 화면/AI 응답에 사용하지
않는다. 모든 파일은 `data/processed/`에 위치하며, 원본 CSV(`data/raw/`, `data/processed/extracted/`)는
이 문서의 대상이 아니다(수정 금지 대상, 참조만 가능).

## 1. `country_profile_base.csv` (23행 — 국가당 1행, A급)

| 컬럼 | 타입 | 의미 | BASE / 주의 |
|---|---|---|---|
| country | string | 국가명(한글) | 23개국 고정 목록 |
| culture_experience_rate_pct | float(%) | E1A-1 문화경험률 | 전체 응답자(n=16,360) |
| culture_experience_rate_base_type | string | 위 지표의 BASE 설명 | "전체 응답자(스크리닝 없음)" |
| hallyu_overall_liking_score | float | 한류 전반 호감도 점수(참고) | 잠재방한객조사 |
| culture_to_korea_positive_pct | float(%) | E4-1 문화→호감도 긍정률 | 문화경험자 하위집합 |
| hallyu_perception_positive_pct | float(%) | 1-35 한류실태 인식긍정률 | **한류실태조사 별도 패널** — 다른 지표와 직접 차감 금지 |
| visit_intention_positive_pct | float(%) | B5B-1 방한의향 있음률 | 전체 응답자(n=16,360) |
| culture_to_visit_positive_pct | float(%) | E4-3 문화→방문의향 긍정률 | 문화경험자 하위집합 |
| top_visit_barrier | string | B13-1A 최다 응답 장벽(집계 마커 제외) | 방문 비의향자 BASE |
| top_visit_barrier_rate_pct | float(%) | 위 장벽의 응답 비율 | 방문 비의향자 BASE |

## 2. `gap_analysis.csv` (23행, A급) — Direct Gap

| 컬럼 | 타입 | 의미 |
|---|---|---|
| country | string | 국가명 |
| culture_experience_rate_pct | float(%) | E1A-1 |
| visit_intention_positive_pct | float(%) | B5B-1 |
| observed_gap_pct_point | float(%p) | `문화경험률 - 방한의향률` (단순 차감, 개인 전환 아님) |
| gap_tier | string | "Gap_큼(상위3분위)" / "Gap_중간(중위3분위)" / "Gap_작음(하위3분위)" — 23개국 상대적 위치 |
| base_type | string | "전체 응답자(잠재방한객조사 일반외국인, n=16,360)" |
| comparability | string | 항상 `direct_within_survey` |

## 3. `conditional_gap_analysis.csv` (23행, A급) — Conditional Gap

| 컬럼 | 타입 | 의미 |
|---|---|---|
| country | string | 국가명 |
| culture_to_korea_positive_pct | float(%) | E4-1 |
| culture_to_visit_positive_pct | float(%) | E4-3 |
| observed_conditional_gap_pct_point | float(%p) | `E4-1 - E4-3` — **`gap_analysis.csv`의 Gap과 별개 축**, 합산 금지 |
| gap_tier | string | 상대적 tercile(위와 동일 방식) |
| base_type | string | "문화경험자(잠재방한객조사, 전체 응답자의 하위집합)" |
| comparability | string | 항상 `conditional` |

## 4. `barrier_pattern_analysis.csv` (23행, A급) — 8개 장벽

| 컬럼 | 타입 | 의미 |
|---|---|---|
| country | string | 국가명 |
| base_type | string | "방문 비의향자(B13-1A, 잠재방한객조사)" |
| sample_n | int | 해당 국가의 방문 비의향자 표본 수 |
| small_sample_flag | "Y"/"N" | 표본 30명 미만 여부 (Y: 베트남·인도네시아·태국·필리핀) |
| 한류_관심_부재 | float(%) | B13-1A 응답 비율 |
| 낮은_한국_인지도 | float(%) | 〃 |
| 부정적_한국_이미지 | float(%) | 〃 |
| 불편한_언어소통 | float(%) | 〃 |
| 여행경비_물가 | float(%) | 〃 |
| 비자_출입국_절차 | float(%) | 〃 |
| 장거리_비행 | float(%) | 〃 |
| 불편한_종교환경 | float(%) | 〃 |

장벽 그룹 매핑(화면 필터용, 원문 항목은 변경하지 않음): 인지/관심={한류_관심_부재, 낮은_한국_인지도},
이미지={부정적_한국_이미지}, 경제/물리적 접근성={여행경비_물가, 장거리_비행}, 제도/언어={비자_출입국_절차,
불편한_언어소통}, 종교/문화환경={불편한_종교환경}.

## 5. `country_bottleneck_profile.csv` (23행, A급) — 병목 프로파일

| 컬럼 | 타입 | 의미 |
|---|---|---|
| country | string | 국가명 |
| direct_gap_pct_point | float(%p) | Direct Gap 값(재인용) |
| direct_gap_type_flag | "Y"/"N" | Type A(Direct Gap 상위3분위) 여부 |
| conditional_gap_pct_point | float(%p) | Conditional Gap 값(재인용) |
| conditional_gap_type_flag | "Y"/"N" | Type B 여부 |
| cognition_interest_barrier_flag | "Y"/"N"/"가능성(소표본 주의)" | Type C 여부 |
| image_barrier_flag | "Y"/"N"/"가능성(소표본 주의)" | Type D 여부 |
| economic_physical_access_barrier_flag | "Y"/"N"/"가능성(소표본 주의)" | Type E 여부 |
| institutional_language_barrier_flag | "Y"/"N"/"가능성(소표본 주의)" | Type F 여부 |
| religious_cultural_env_barrier_flag | "Y"/"N"/"가능성(소표본 주의)" | Type G 여부 |
| small_sample_barrier_note | "Y"/"N" | 이 국가에 소표본 주의가 하나라도 붙었는지 |
| key_observed_pattern | string | 충족한 유형과 트리거된 세부 장벽을 나열한 서술 문장(세미콜론 구분) — **그대로 인용, 재요약 금지** |
| interpretation_caution | string | BASE 차이/소표본 관련 고정 주의문 — **그대로 인용, 임의 수정 금지** |

## 6. `bottleneck_type_summary.csv` (7행, B급) — 유형별 요약

| 컬럼 | 타입 | 의미 |
|---|---|---|
| type_code | string | Type A~G |
| type_label | string | 유형 한글 라벨 |
| criterion | string | 판정 기준 원문 |
| n_countries | int | 소속 국가 수 |
| pct_of_23 | float(%) | 23개국 대비 비율 |
| country_list | string | 소속 국가 목록(세미콜론 구분) |
| n_also_in_other_type | int | 다른 유형에도 동시 소속된 국가 수 |
| major_barrier_detail | string | 그룹 내 개별 장벽별 트리거 국가 수 |
| prior_gap_consistency_note | string | Type A와의 중복 등 참고 서술 |
| overly_broad_flag | "Y"/"N" | 23개국의 65% 이상을 포함하는지(구별력 경고) |

## 7. `gap_barrier_correlation.csv` (18행, B급) — 상관표

| 컬럼 | 타입 | 의미 |
|---|---|---|
| pair | string | 비교 대상 두 변수 |
| subset | string | "전체_23개국" 또는 "소표본4개국_제외(n=19)" |
| n | int | 표본 수 |
| pearson_r / pearson_p | float | Pearson 상관/유의확률 |
| spearman_r / spearman_p | float | Spearman 상관/유의확률 |
| direction | string | "양(+)의 방향" / "음(-)의 방향" / "뚜렷한 방향 없음" — **"유의함" 여부 판정어 아님** |

주의: 이 표의 어떤 r/p 값도 "원인"·"영향"·"효과"로 재서술하지 않는다.

## 8. `sensitivity_analysis.csv` (9행, B급) — 소표본 민감도

| 컬럼 | 타입 | 의미 |
|---|---|---|
| pair | string | 비교 대상 두 변수 |
| n_full / pearson_r_full / pearson_p_full | - | 23개국 전체 결과 |
| n_excl / pearson_r_excl / pearson_p_excl | - | 소표본 4개국 제외(n=19) 결과 |
| pearson_r_diff | float | 두 조건의 r 차이 |
| direction_changed | "Y"/"N" | 소표본 제외로 상관 방향이 반전됐는지 |

## 9. `country_indicator_distribution.csv` (5행, B급) — 핵심 지표 분포

컬럼: `indicator, table_id, layer, comparability, base_type, n_countries, min, q1, median, q3, max, mean,
stdev`. Overview 화면의 dot plot 배경 통계로 사용.

## 10. `country_pattern_profile.csv` (23행, B급) — tercile 프로파일 원본

`country_profile_base.csv`의 5개 핵심 지표 각각에 대해 `_tier` 컬럼(하위/중위/상위3분위)이 추가된 버전.
Country Explorer의 "tercile 위치" 표시에 사용.

## 11. `country_bottleneck_observations.csv` (25행, C급) — 서술형 관찰 로그

컬럼: `country, comparability_class, observation_type, detail, confidence`. AI가 "왜 이런 패턴이
관찰됐다고 하는지"를 설명할 때 근거 문장으로만 인용(대시보드 기본 화면 비노출).

## 12. `analysis_long.csv` (5,658행, C급) — 원천 롱포맷

컬럼: `country, layer, source_survey, table_id, indicator, response_option, base_type, sample_n, value,
unit, comparability, note`. 모든 상위 CSV의 계산 원천. 대시보드에 직접 노출하지 않되, AI가 "이 수치가
어느 표(table_id)에서 나왔는지" 답할 때 조회 대상으로 사용 가능.

## 13. `tables_17_18_37_key_values_clean.csv` (17,960행, C급) — 콘텐츠 호감/비호감·부정인식 이유

2026-08-26 추가. 8개 방문 장벽(%)의 "왜"를 설문이 직접 묻지 않아 생긴 공백을 메우기 위해
표 1-17/1-18/1-37을 추가로 OCR 추출했다. `analysis_long.csv`와 마찬가지로 롱포맷 원천이며,
대시보드 기본 화면에 노출하지 않고 AI가 "왜 그런지" 설명할 때 근거로 조회한다.

| 컬럼 | 타입 | 의미 |
|---|---|---|
| country | string | 국가명 |
| table_id | string | "1-17"(호감요인) / "1-18"(호감 저해요인) / "1-37"(한류 부정적 인식 공감 이유) |
| indicator | string | 표 이름 한글 |
| content_category | string | 콘텐츠 카테고리(드라마/예능/영화/음악/애니메이션/출판물/웹툰/게임/패션/뷰티/음식/한국어). **1-37은 이 값이 없음**(카테고리 구분 없는 단일 문항) |
| item | string | 이유 항목 텍스트. OCR 라벨을 빈도 기반으로 정규화한 것(`clean_labels_17_18_37.py`) — `label_confidence` 참고 |
| raw_item | string | 정규화 전 원본 OCR 텍스트(참고용, 원본 추적 목적) |
| rank_group | string | "1순위" / "1+2순위(중복)" — 1-16/33/35/41과 달리 이 표는 순위 응답형이라 두 종류 값이 공존 |
| value | float(%) | 해당 항목 응답 비율 |
| base | int | (사례수) — 카테고리/문항 블록별 BASE |
| label_confidence | string | "high_confidence"(같은 라벨이 20회 이상 반복 확인됨) / "low_confidence"(OCR 잡음으로 라벨을 신뢰하기 어려움 — **value는 유효하나 item 텍스트는 화면에 그대로 노출하지 말 것**) |
| verification_status | string | "auto_extracted" / "manual_review" (1순위/1+2순위 병합 실패 등 — 값은 보존되나 rank_group 확정도가 낮음) |
| source_page | string | 원본 PDF 페이지 번호(쉼표구분) |

**주의**:
- 1-17/1-18의 BASE는 "방문 비의향자"가 아니라 **해당 콘텐츠 카테고리 경험/인지자**다(barrier_pattern_analysis.csv와 BASE가 다름 — 직접 차감하거나 같은 모집단처럼 섞지 않는다).
- `label_confidence`가 "low_confidence"인 행은 값 자체(%)는 유효하지만 어떤 항목인지 텍스트로 단정하지 말고, 인용할 때 "정확한 항목명은 불확실하나 이런 응답이 있었다" 수준으로만 서술한다.

## 공통 규칙

- 모든 퍼센트 값은 소수점 표시 여부와 무관하게 **국가 단위 응답 비율**이며, 개인 단위 확률이 아니다.
- `gap_tier`, `*_tier`, `overly_broad_flag` 등 tercile/구간 관련 필드는 23개국 사이의 **상대적 위치**이며
  절대적 기준값이 아니다.
- `Y`/`N`/`가능성(소표본 주의)` 3값 플래그는 대시보드에서 반드시 3가지 상태로 구분 표시한다(소표본 주의를
  단순 "Y"로 뭉개지 않는다).
- 이 딕셔너리에 없는 새 컬럼을 계산해 화면에 추가하지 않는다. 새 지표가 필요하면 먼저
  `final_analysis_framework.md`를 갱신하는 별도 분석 단계를 거친다.
