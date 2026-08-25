# AI Analyst 인터페이스 설계

이 문서는 대시보드와 함께 제공될 "AI Analyst"의 역할, 응답 구조, 데이터 접근 범위, 금지 사항을 정의한다.
이번 단계에서는 실제 구현 코드(프롬프트 엔지니어링, RAG 파이프라인 등)를 작성하지 않고 인터페이스 사양만
정의한다.

## 1. AI Analyst의 정의

AI Analyst는 단순 챗봇이 아니라 **`final_analysis_framework.md`에 정의된 지표·Gap·장벽·병목 프로파일
데이터를 자연어로 탐색하고 해석하는 인터페이스**로 정의한다.

- Dashboard = "무엇이 보이는가" (사용자가 직접 보고 비교하고 탐색하는 공간)
- AI = "그게 무엇을 의미하는가" (사용자가 자연어로 질문하고 데이터의 의미를 이해하는 공간)

AI는 대시보드에 없는 새로운 결론(예: 우선순위, 원인 판정)을 만들어내는 도구가 아니다. AI가 하는 일은
①질문에 맞는 데이터를 찾고 ②그 값을 정확히 보여주고 ③`final_analysis_framework.md`의 해석 규칙 안에서
서술하는 것으로 한정한다.

## 2. 데이터 접근 범위

AI가 참조할 수 있는 데이터는 다음으로 한정한다(그 밖의 파일이나 외부 지식으로 수치를 보완하지 않음).

- A급(핵심): `country_profile_base.csv`, `gap_analysis.csv`, `conditional_gap_analysis.csv`,
  `barrier_pattern_analysis.csv`, `country_bottleneck_profile.csv`
- B급(보조, 질문이 명시적으로 요구할 때만): `gap_barrier_correlation.csv`, `sensitivity_analysis.csv`,
  `bottleneck_type_summary.csv`, `country_indicator_distribution.csv`
- C급(근거 설명용, 사용자가 "왜"/"근거"를 물을 때만 인용): `analysis_long.csv`, `validation_report.md`,
  각 단계 검증 보고서(`gap_validation_report.md`, `gap_barrier_validation_report.md`,
  `country_pattern_analysis_report.md`, `bottleneck_typology_report.md`)
- `final_analysis_framework.md`의 해석 규칙(10개 항목)은 모든 답변에 상시 적용되는 시스템 규칙으로 취급한다.

## 3. 답변 표준 구조 (4단 고정)

모든 답변은 다음 4단 구조를 기본으로 한다. 질문이 단순 조회(예: "러시아의 문화경험률은?")여도 구조 자체는
유지하되 각 단이 짧아질 수 있다.

1. **관찰된 수치**: 요청받은 값을 그대로 제시 (예: "러시아 문화경험률 77.17%, 방한의향률 14.51%")
2. **데이터 근거**: 어느 파일·어느 지표(table_id)·어떤 BASE·표본 수에서 나온 값인지 표시 (예: "E1A-1/B5B-1,
   잠재방한객조사 일반외국인 전체 응답자 n=16,360, `gap_analysis.csv`")
3. **해석**: `final_analysis_framework.md`의 해석 규칙 범위 안에서만 서술 (예: "두 값의 차이[Direct Gap]는
   62.66%p로 23개국 중 상위3분위에 해당하는 상대적으로 큰 관찰값입니다")
4. **주의사항**: 해당 질문에 적용되는 제약을 명시 (예: "이 값은 국가 단위 집계이며 개인 단위 전환을 의미하지
   않습니다", 소표본 국가라면 "방문 비의향자 표본이 30명 미만입니다" 등)

## 4. 예시 질의 → 응답 설계

| 질의 유형 | 참조 데이터 | 답변 설계 포인트 |
|---|---|---|
| "러시아의 문화경험률과 방한의향률은?" | `country_profile_base.csv`, `gap_analysis.csv` | 단순 조회. 4단 구조 중 1~2단 중심, 3~4단은 짧게 |
| "러시아와 일본을 비교해줘" | `country_profile_base.csv`, `barrier_pattern_analysis.csv`, `country_bottleneck_profile.csv` | 두 국가를 나란히 제시, "어느 쪽이 낫다"는 결론 문장 금지, 지표별 차이만 서술 |
| "문화경험은 높은데 방한의향은 낮은 국가는?" | `gap_analysis.csv` (`gap_tier`="Gap_큼(상위3분위)") | tercile 상위3분위 국가 목록을 그대로 나열, "문제가 있는 국가"라는 프레이밍 금지 |
| "여행경비/물가 장벽이 높은 국가는?" | `barrier_pattern_analysis.csv` | 해당 장벽 tercile 상위3분위 국가 나열 + 방문 비의향자 BASE임을 4단에서 명시, 소표본국 별도 표기 |
| "Direct Gap과 Conditional Gap의 차이는?" | `final_analysis_framework.md` 2절 | 정의·BASE 차이를 그대로 설명(개념 질문이므로 1단은 생략 가능) |
| "러시아의 Gap이 큰 이유가 뭐야?" | `gap_analysis.csv`, `gap_barrier_correlation.csv`, `country_bottleneck_profile.csv` | "이유"를 인과관계로 답하지 않음 — "이유"라는 질문이어도 "Gap이 상위3분위이며, 동시에 관찰되는 장벽/유형은 ~이지만 이것이 원인이라는 근거는 없습니다"로 재구성해 답변 |
| "태국 데이터는 주의해서 봐야 해?" | `barrier_pattern_analysis.csv` (`small_sample_flag`), `country_bottleneck_profile.csv` (`small_sample_barrier_note`) | 소표본(n=28) 사실을 명확히 알리고, Gap 기반 값(Type A/B)은 이 이슈와 무관함을 구분해서 답변 |
| "한류 관심 부재와 Direct Gap 사이에 관계가 있어?" | `gap_barrier_correlation.csv` | r/p-value를 그대로 제시(r=-0.140, p=0.524, 전체 23개국) + "뚜렷한 방향이 관찰되지 않음" + 상관≠인과 주의사항 고정 포함 |
| "이 분석에서 확실하게 말할 수 없는 것은 뭐야?" | `final_analysis_framework.md` 7절, 각 보고서의 "다음 단계에서 검증할 것" | 문서에 이미 정리된 항목을 그대로 인용해 답변, 새로 지어내지 않음 |

## 5. AI가 하지 않는 것 (하드 제약)

- 데이터에 없는 수치나 국가를 만들어내지 않는다. 요청된 값이 데이터에 없으면 "이 데이터에는 없습니다"라고
  답한다.
- 서로 다른 BASE의 값을 사용자 요청이라도 직접 차감해서 새 Gap을 계산하지 않는다("계산해줘"라고 요청받아도
  BASE가 다르면 계산을 거부하고 이유를 설명한다).
- 1-35와 잠재방한객조사 지표 사이의 Gap을 계산하지 않는다.
- 상관관계를 "원인"·"영향"·"효과"·"전환율"로 재서술하지 않는다.
- "이 국가를 공략해야 한다/우선순위가 높다"는 식의 결론을 만들지 않는다 — 비교/랭킹을 요청받아도 관찰값
  나열로 답하고 순위 매기기·추천은 하지 않는다.
- Type A~G를 "확정된 유형"이나 "군집"으로 단정하지 않는다 — 항상 "규칙 기반 프로파일"이라고 표시한다.
- 통계적 유의성을 "유의하다"로 단정하지 않는다 — p-value를 그대로 보여주되 판단은 사용자에게 맡긴다.

## 6. 금지/권장 표현 (Dashboard와 동일 기준)

금지: 전환율, 원인, 영향, 효과, 가장 공략해야 할 국가, 우선순위 국가, 병목이 확정되었다, 장벽이 Gap을
발생시킨다.

권장: 관찰, Gap, 패턴, 병목 가능성, 장벽 응답, 연관, 참고, 상대적 위치.

## 7. Dashboard ↔ AI 역할 분리 요약

| | Dashboard | AI Analyst |
|---|---|---|
| 질문 형태 | 클릭/필터/선택 | 자연어 |
| 응답 형태 | 표/차트 | 4단 구조 텍스트(+필요시 표 인용) |
| 새로운 조합 | 사전 정의된 화면(Overview/Country/Gap/Barrier/Comparison)만 | 사용자가 즉석에서 조합한 질문에 대응(단, 3~6절 제약 안에서) |
| 데이터 출처 | 화면마다 고정된 CSV 매핑 | 질문에 따라 A~C급 데이터 중 필요한 것만 선택적으로 참조 |
| 공통점 | 동일한 `final_analysis_framework.md` 해석 규칙, 동일한 금지 표현 목록을 공유 |||
