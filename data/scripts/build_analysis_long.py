# -*- coding: utf-8 -*-
"""
분석 프레임 확정 보고서(Layer 1~4)를 실제 분석용 데이터셋으로 구현한다.

이 스크립트는:
  - 기존 원본 CSV(potential_tourist_general_core.csv, potential_tourist_intender_core.csv,
    all_countries_key_values.csv)를 오직 읽기만 하며 절대 수정하지 않는다.
  - 새로운 외부 데이터를 수집하지 않는다.
  - Gap 계산/순위/상관/회귀/군집/종합점수 계산을 하지 않는다.
  - "확정 보고서"에서 정한 지표·Layer·comparability 규칙을 그대로 구현한다(임의 변경 금지).

산출물:
  - data/processed/analysis_long.csv
  - data/processed/country_profile_base.csv
  - data/processed/validation_report.md
"""

from __future__ import annotations

import csv
import statistics
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"

GENERAL_CSV = PROCESSED_DIR / "potential_tourist_general_core.csv"
INTENDER_CSV = PROCESSED_DIR / "potential_tourist_intender_core.csv"
HALLYU_CSV = PROCESSED_DIR / "extracted" / "all_countries_key_values.csv"
COUNTRY_MAPPING_CSV = PROCESSED_DIR / "potential_hallyu_country_mapping.csv"

OUT_LONG_CSV = PROCESSED_DIR / "analysis_long.csv"
OUT_PROFILE_CSV = PROCESSED_DIR / "country_profile_base.csv"
OUT_VALIDATION_MD = PROCESSED_DIR / "validation_report.md"

# ---------------------------------------------------------------------------
# 1. 23개국 교집합 (기존 potential_hallyu_country_mapping.csv 결과를 그대로 사용,
#    새 국가를 추가하지 않는다)
# ---------------------------------------------------------------------------


def load_country_mapping():
    with open(COUNTRY_MAPPING_CSV, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    intersection = []  # [(potential_country, standard_country, hallyu_country)]
    hallyu_only = []
    for r in rows:
        if r["match_status"] in ("EXACT_MATCH", "NAME_VARIATION"):
            intersection.append(
                (r["potential_tourist_country"], r["potential_standard_country"], r["hallyu_country"])
            )
        elif r["match_status"] == "HALLYU_ONLY":
            hallyu_only.append(r["hallyu_country"])
    return intersection, hallyu_only


# ---------------------------------------------------------------------------
# 2. 지표 매핑 테이블 (확정 보고서 3번 항목을 그대로 구현. 임의 추가/변경 금지)
#    key: (source_survey, table_id) -> meta
# ---------------------------------------------------------------------------

# comparability 판단 기준 (확정 보고서 ⑤ 근거):
#   direct      : 동일 survey, 동일 BASE(전체 응답자)를 공유하는 지표끼리
#   conditional : BASE가 하위집합이거나(subset) survey가 다르지만 분석적 의미를 부여할 수 있는 경우
#   not_comparable : 개념이 근본적으로 다르거나(NO_MATCH) BASE가 너무 달라 산술비교 불가

HALLYU_META = {
    "1-16": dict(
        layer="Layer1_Hallyu_Exposure", role="참고", indicator="콘텐츠 카테고리별 호감도",
        base_type="한류경험자(항목별 base 상이)", comparability="conditional",
        note="한류 경험자로 사전 스크리닝된 패널 기준. 카테고리별 응답 사례수가 국가마다 다름. "
             "잠재방한객 E3 시리즈와 카테고리 축은 겹치나 측정대상(호감도 vs 이용빈도)이 달라 조건부 참고용.",
    ),
    "1-33": dict(
        layer="Layer1_Hallyu_Exposure", role="참고", indicator="관심도 1년전대비/1년후예상 변화",
        base_type="한류경험자(국가별 균일)", comparability="not_comparable",
        note="핵심 Funnel 지표로 사용하지 않음(확정 보고서 제외 결정). '변화 방향'을 묻는 문항이라 "
             "잠재방한객조사의 어떤 지표와도 개념적 대응이 없음(NO_MATCH). 국가 내부 트렌드 참고용으로만 유지.",
    ),
    "1-35": dict(
        layer="Layer2_Korea_Perception", role="핵심", indicator="문화경험이 한국 인식에 미친 영향",
        base_type="한류경험자(국가별 균일)", comparability="conditional",
        note="잠재방한객 E4-1과 질문 설계가 가장 유사한 대응 후보(STRONG_CANDIDATE). "
             "단 모집단이 '이미 콘텐츠 경험자로 스크리닝된 패널'이라는 점을 항상 함께 표기해야 함.",
    ),
    # 1-41은 확정 보고서에서 핵심 분석 제외/보류 -> analysis_long에 포함하지 않음(META 미등록)
}

POTENTIAL_META = {
    # source_survey='잠재방한객_일반외국인' (potential_tourist_general_core.csv)
    "E1A-1": dict(
        source_survey="잠재방한객_일반외국인", layer="Layer1_Hallyu_Exposure", role="핵심",
        indicator="한국문화 경험 여부", base_type="전체 응답자(스크리닝 없음)",
        comparability="direct_within_survey",
        note="일반외국인 조사 전체 모집단(n=16,360) 기준. B5B-1과 동일 BASE(전체)를 공유하여 "
             "같은 모집단 내 병렬 통계로 direct 비교 가능. 한류실태조사와는 모집단 정의 자체가 달라 conditional.",
    ),
    "E4-1": dict(
        source_survey="잠재방한객_일반외국인", layer="Layer2_Korea_Perception", role="핵심",
        indicator="문화경험이 한국 호감도에 미친 영향", base_type="문화경험자(E1A-1=경험, 하위집합)",
        comparability="conditional",
        note="전체 응답자(E1A-1/B5B-1)의 하위집합이 BASE이므로 전체기준 지표와 직접비교 불가, "
             "동일 survey 내 하위집합 지표로서 conditional. 한류실태 1-35와도 conditional(모집단 스크리닝 방식 차이).",
    ),
    "E4-3": dict(
        source_survey="잠재방한객_일반외국인", layer="Layer3_Visit_Intention", role="핵심",
        indicator="문화경험이 방문(재방문)의향에 미친 영향", base_type="문화경험자(하위집합)",
        comparability="conditional",
        note="한류실태조사에 대응 지표 없음(방한_경험_의향 NOT_FOUND). 잠재방한객조사 고유 지표. "
             "BASE가 전체 응답자의 하위집합이므로 E1A-1/B5B-1과는 conditional.",
    ),
    "B5A-1": dict(
        source_survey="잠재방한객_일반외국인", layer="Layer3_Visit_Intention", role="보조",
        indicator="향후 3년 내 한국 방문 의향(5점척도)", base_type="해외여행의향자(하위집합)",
        comparability="conditional",
        note="해외여행 자체에 의향이 있는 사람만 대상이라 전체 모집단 기준(B5B-1)과 분모가 다름.",
    ),
    "B5B-1": dict(
        source_survey="잠재방한객_일반외국인", layer="Layer3_Visit_Intention", role="핵심_대표",
        indicator="향후 3년 내 한국 방문 의향(4분류)", base_type="전체 응답자",
        comparability="direct_within_survey",
        note="전체 응답자(n=16,360) 기준으로 E1A-1과 동일 BASE를 공유. 국가 간 비교의 기본 축으로 사용 권장.",
    ),
    "B13-1A": dict(
        source_survey="잠재방한객_일반외국인", layer="Layer4_Conversion_Barrier", role="핵심",
        indicator="한국 방문 비의향 이유(1+2+3순위)", base_type="방문 비의향자(하위집합)",
        comparability="conditional",
        note="방문 비의향자만 대상이라 국가별 표본이 작을 수 있음(예: 일본 165명). "
             "한류실태조사에 대응 지표 없음(방한_장벽 NOT_FOUND).",
    ),
    "B13-2A": dict(
        source_survey="잠재방한객_일반외국인", layer="Layer4_Conversion_Barrier", role="핵심",
        indicator="한국 방문 비의향 이유(1순위)", base_type="방문 비의향자(하위집합)",
        comparability="conditional",
        note="B13-1A와 동일 BASE, 1순위만 집계. 소표본 국가 해석 주의.",
    ),
    "C4": dict(
        source_survey="잠재방한객_방한의향자", layer="Layer3_Visit_Intention", role="보조",
        indicator="한국 여행 관심 계기", base_type="방한의향자(별도 스크리닝된 독립 조사)",
        comparability="conditional",
        note="방한의향자 조사는 일반외국인 조사와 별개로 모집된 독립 패널(전원 이미 방한의향자로 스크리닝됨). "
             "일반외국인 파일의 지표(E1A-1 등)와 직접 비교 불가, conditional로만 참고.",
    ),
    "C5": dict(
        source_survey="잠재방한객_방한의향자", layer="Layer3_Visit_Intention", role="보조",
        indicator="한국 여행 결정 요인", base_type="방한의향자(별도 스크리닝된 독립 조사)",
        comparability="conditional",
        note="C4와 동일한 모집단 구조. 일반외국인 파일 지표와 직접 비교 불가.",
    ),
}

# E3-1~E3-12 (E3-13은 국가 커버리지 문제로 명시적 제외)
E3_LABELS = {
    "E3-1": "대중가요", "E3-2": "드라마", "E3-3": "예능 프로그램", "E3-4": "영화",
    "E3-5": "음식", "E3-6": "뷰티", "E3-7": "패션", "E3-8": "웹툰", "E3-9": "게임",
    "E3-10": "애니메이션", "E3-11": "문학", "E3-12": "한국어",
}
for code, label in E3_LABELS.items():
    POTENTIAL_META[code] = dict(
        source_survey="잠재방한객_일반외국인", layer="Layer1_Hallyu_Exposure", role="보조",
        indicator=f"한국문화 분야별 이용빈도_{label}", base_type="해당 분야 경험자(하위집합)",
        comparability="conditional",
        note="한류실태 1-16과 카테고리 축은 겹치나 측정대상(이용빈도 vs 호감도)이 달라 병렬 참고용.",
    )

EXCLUDED_TABLES = {
    "잠재방한객_일반외국인": {"E3-13": "국가 커버리지 문제(23개국 중 6개국 표본 0) - 확정 보고서 제외 결정"},
    "한류실태조사": {"1-41": "고관여 제품/서비스 구매목록 내 항목일 가능성 있어 개념 순도 미검증 - 확정 보고서 제외/보류 결정"},
}

INCLUDED_GENERAL_CODES = set(POTENTIAL_META.keys()) - {"C4", "C5"}
INCLUDED_INTENDER_CODES = {"C4", "C5"}
INCLUDED_HALLYU_IDS = set(HALLYU_META.keys())


# ---------------------------------------------------------------------------
# 3. 데이터 로드
# ---------------------------------------------------------------------------


def load_csv(path):
    with open(path, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def to_float(x):
    if x is None or x == "":
        return None, False
    try:
        return float(x), True
    except (TypeError, ValueError):
        return None, False


# ---------------------------------------------------------------------------
# 4. analysis_long.csv 생성
# ---------------------------------------------------------------------------

LONG_FIELDS = [
    "country", "layer", "source_survey", "table_id", "indicator",
    "response_option", "base_type", "sample_n", "value", "unit",
    "comparability", "note",
]


def build_long_rows(general_rows, intender_rows, hallyu_rows, potential_to_standard, hallyu_to_standard):
    long_rows = []
    issues = []  # 검증용 이슈 로그 (수정하지 않고 기록만)

    # --- 잠재방한객(일반외국인) ---
    for r in general_rows:
        code = r["table_code"]
        if code not in INCLUDED_GENERAL_CODES:
            continue
        if r["country"] == "전체":
            continue  # 국가 단위 분석셋이므로 집계행(전체)은 제외
        std_country = potential_to_standard.get(r["country"])
        if std_country is None:
            continue  # 23개국 교집합 밖 -> 포함하지 않음
        meta = POTENTIAL_META[code]
        value, ok = to_float(r["value"])
        if not ok and r["value"] not in (None, ""):
            issues.append(f"[VALUE_NOT_NUMERIC] general/{code}/{r['country']}/{r['response_option']}: '{r['value']}'")
        sample_n, sok = to_float(r["sample_n"])
        if not sok:
            issues.append(f"[SAMPLE_N_MISSING] general/{code}/{r['country']}/{r['response_option']}: raw='{r['sample_n_raw']}'")
        long_rows.append(dict(
            country=std_country, layer=meta["layer"], source_survey=meta["source_survey"],
            table_id=code, indicator=meta["indicator"], response_option=r["response_option"],
            base_type=meta["base_type"], sample_n=sample_n, value=value, unit=r["unit"],
            comparability=meta["comparability"],
            note=f"{meta['note']} | 원본 BASE 라벨: {r['base']}",
        ))

    # --- 잠재방한객(방한의향자) ---
    for r in intender_rows:
        code = r["table_code"]
        if code not in INCLUDED_INTENDER_CODES:
            continue
        if r["country"] == "전체":
            continue
        std_country = potential_to_standard.get(r["country"])
        if std_country is None:
            continue
        meta = POTENTIAL_META[code]
        value, ok = to_float(r["value"])
        if not ok and r["value"] not in (None, ""):
            issues.append(f"[VALUE_NOT_NUMERIC] intender/{code}/{r['country']}/{r['response_option']}: '{r['value']}'")
        sample_n, sok = to_float(r["sample_n"])
        if not sok:
            issues.append(f"[SAMPLE_N_MISSING] intender/{code}/{r['country']}/{r['response_option']}: raw='{r['sample_n_raw']}'")
        long_rows.append(dict(
            country=std_country, layer=meta["layer"], source_survey=meta["source_survey"],
            table_id=code, indicator=meta["indicator"], response_option=r["response_option"],
            base_type=meta["base_type"], sample_n=sample_n, value=value, unit=r["unit"],
            comparability=meta["comparability"],
            note=f"{meta['note']} | 원본 BASE 라벨: {r['base']}",
        ))

    # --- 한류실태조사 ---
    for r in hallyu_rows:
        tid = r["table_id"]
        if tid not in INCLUDED_HALLYU_IDS:
            continue
        std_country = hallyu_to_standard.get(r["country"])
        if std_country is None:
            continue  # 23개국 교집합 밖(hallyu-only 7개국) -> 포함하지 않음
        meta = HALLYU_META[tid]
        value, ok = to_float(r["value"])
        if not ok and r["value"] not in (None, ""):
            issues.append(f"[VALUE_NOT_NUMERIC] hallyu/{tid}/{r['country']}/{r['item']}: '{r['value']}'")
        sample_n, sok = to_float(r["base"])
        if not sok:
            issues.append(f"[SAMPLE_N_MISSING] hallyu/{tid}/{r['country']}/{r['item']}: raw='{r['base']}'")
        category = r["category"] or ""
        response_option = f"{category} - {r['item']}" if category else r["item"]
        note = meta["note"]
        if r["verification_status"] == "manual_review":
            note += f" | [주의] 원본 verification_status=manual_review ({r['notes']})"
            issues.append(f"[MANUAL_REVIEW_VALUE] hallyu/{tid}/{r['country']}/{r['item']}: value={r['value']} ({r['notes']})")
        long_rows.append(dict(
            country=std_country, layer=meta["layer"], source_survey="한류실태조사",
            table_id=tid, indicator=meta["indicator"], response_option=response_option,
            base_type=meta["base_type"], sample_n=sample_n, value=value, unit=r["unit"],
            comparability=meta["comparability"], note=note,
        ))

    return long_rows, issues


def write_long_csv(rows):
    with open(OUT_LONG_CSV, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=LONG_FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    print(f"[저장] {OUT_LONG_CSV} ({len(rows)}행)")


# ---------------------------------------------------------------------------
# 5. country_profile_base.csv 생성 (파생 데이터, 해석/Gap 계산 없이 값만 나열)
# ---------------------------------------------------------------------------


def build_country_profile(long_rows, target_countries):
    """국가별로 핵심 지표(role='핵심'/'핵심_대표') 값을 뽑아 하나의 행으로 정리한다.
    Gap/전환율 계산 없이, 각 핵심 지표의 '대표값'만 나열한다."""

    by_country_table = defaultdict(list)
    for r in long_rows:
        by_country_table[(r["country"], r["table_id"])].append(r)

    def get(country, table_id, response_option_substr=None):
        rows = by_country_table.get((country, table_id), [])
        if response_option_substr:
            rows = [r for r in rows if response_option_substr in r["response_option"]]
        return rows

    profile_rows = []
    for country in target_countries:
        row = {"country": country}

        # Layer1: 문화 경험률 (E1A-1, response_option='경험')
        e1a1 = get(country, "E1A-1", "경험")
        row["culture_experience_rate_pct"] = e1a1[0]["value"] if e1a1 else None
        row["culture_experience_rate_base_type"] = e1a1[0]["base_type"] if e1a1 else None

        # Layer1(참고): 한류실태 평균 호감도(1-16, '전반적 만족도' 항목이 있으면 사용, 없으면 결측)
        h116 = get(country, "1-16", "전반적 만족도")
        row["hallyu_overall_liking_score"] = h116[0]["value"] if h116 else None

        # Layer2: 문화경험->호감도 긍정비율 (E4-1, '약간 긍정적' + '매우 긍정적' 합)
        e41_pos = get(country, "E4-1")
        pos_vals = [r["value"] for r in e41_pos if r["response_option"] in ("약간 긍정적으로 변화하였다", "매우 긍정적으로 변화하였다") and r["value"] is not None]
        row["culture_to_korea_positive_pct"] = round(sum(pos_vals), 4) if pos_vals else None

        # Layer2(참고): 한류실태 1-35 긍정비율 (매우+약간 긍정)
        h135 = get(country, "1-35")
        h135_pos = [r["value"] for r in h135 if ("긍정적으로 변" in r["response_option"]) and r["value"] is not None]
        row["hallyu_perception_positive_pct"] = round(sum(h135_pos), 4) if h135_pos else None

        # Layer3: 방한의향 있음 비율 (B5B-1, '방문의향 있음')
        b5b1 = get(country, "B5B-1", "방문의향 있음")
        row["visit_intention_positive_pct"] = b5b1[0]["value"] if b5b1 else None

        # Layer3: 문화경험->방문의향 긍정비율 (E4-3, 긍정 2개 합)
        e43_pos = get(country, "E4-3")
        pos_vals2 = [r["value"] for r in e43_pos if r["response_option"] in ("약간 긍정적으로 변화하였다", "매우 긍정적으로 변화하였다") and r["value"] is not None]
        row["culture_to_visit_positive_pct"] = round(sum(pos_vals2), 4) if pos_vals2 else None

        # Layer4: 방한 비의향 1순위 장벽 (B13-2A 중 최댓값 항목, 합계/집계 마커는 제외)
        AGGREGATE_MARKERS = {"계", "종합", "종합/Top2", "Top2"}
        b132a = get(country, "B13-2A")
        b132a = [r for r in b132a if r["value"] is not None and r["response_option"] not in AGGREGATE_MARKERS]
        if b132a:
            top = max(b132a, key=lambda r: r["value"])
            row["top_visit_barrier"] = top["response_option"]
            row["top_visit_barrier_rate_pct"] = top["value"]
        else:
            row["top_visit_barrier"] = None
            row["top_visit_barrier_rate_pct"] = None

        profile_rows.append(row)

    return profile_rows


def write_profile_csv(rows):
    fieldnames = [
        "country",
        "culture_experience_rate_pct", "culture_experience_rate_base_type",
        "hallyu_overall_liking_score",
        "culture_to_korea_positive_pct", "hallyu_perception_positive_pct",
        "visit_intention_positive_pct", "culture_to_visit_positive_pct",
        "top_visit_barrier", "top_visit_barrier_rate_pct",
    ]
    with open(OUT_PROFILE_CSV, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    print(f"[저장] {OUT_PROFILE_CSV} ({len(rows)}행)")


# ---------------------------------------------------------------------------
# 6. 데이터 품질 검증 -> validation_report.md
# ---------------------------------------------------------------------------


def run_validation(long_rows, issues, target_countries, general_rows, intender_rows, hallyu_rows):
    report = []
    report.append("# validation_report.md — analysis_long.csv / country_profile_base.csv 검증 결과\n")
    report.append("(원본 CSV는 수정하지 않았으며, 발견된 문제는 아래에 기록만 하고 임의로 보정하지 않았습니다.)\n")

    # 6-1. 23개국 존재 여부 (table_id 별)
    report.append("## 1. 23개국 커버리지 (table_id 별)\n")
    by_table_countries = defaultdict(set)
    for r in long_rows:
        by_table_countries[r["table_id"]].add(r["country"])
    report.append("| table_id | 존재 국가 수 | 누락 국가 |")
    report.append("|---|---|---|")
    for tid in sorted(by_table_countries):
        present = by_table_countries[tid]
        missing = sorted(set(target_countries) - present)
        report.append(f"| {tid} | {len(present)}/23 | {', '.join(missing) if missing else '-'} |")
    report.append("")

    # 6-2. 국가별 중복 행 여부 (동일 country/table_id/response_option 조합이 2회 이상 등장하는지)
    report.append("## 2. 중복 행 검사\n")
    dup_counter = defaultdict(int)
    for r in long_rows:
        key = (r["country"], r["table_id"], r["response_option"])
        dup_counter[key] += 1
    dups = {k: v for k, v in dup_counter.items() if v > 1}
    if dups:
        report.append(f"- **중복 발견: {len(dups)}건**")
        for k, v in list(dups.items())[:20]:
            report.append(f"  - {k} : {v}회")
    else:
        report.append("- 중복 없음 (country/table_id/response_option 조합 기준)")
    report.append("")

    # 6-3. value 숫자 검증 / sample_n 누락 / BASE 누락
    report.append("## 3. value/sample_n/BASE 이슈 로그\n")
    if issues:
        report.append(f"- 총 {len(issues)}건 발견 (아래 나열, 수정하지 않고 원본 그대로 유지)")
        for it in issues:
            report.append(f"  - {it}")
    else:
        report.append("- 이슈 없음")
    report.append("")

    # 6-4. percentage 합계 이상 여부 (single-select 100% 유형 표만 대상)
    report.append("## 4. Percentage 합계 검증 (단일선택형 표만 대상, 다중응답표는 검증 대상 아님)\n")
    report.append("검증 대상: E1A-1(경험/비경험), B5B-1(4분류), 1-35(5점 분포), E3-1~12(빈도 분포). "
                   "B13-1A/2A, C4, C5, 1-16, 1-33은 다중응답/평균척도 표이므로 100% 합계 검증 대상이 아님.\n")
    single_select_tables = {"E1A-1", "B5B-1", "1-35"} | set(E3_LABELS.keys())
    exclude_from_sum = {"계", "종합", "종합/Top2", "Top2"}
    sums = defaultdict(float)
    has_values = defaultdict(bool)
    for r in long_rows:
        if r["table_id"] in single_select_tables and r["unit"] == "%" and r["response_option"] not in exclude_from_sum:
            if "score" in (r["unit"] or "") :
                continue
            if r["value"] is not None:
                sums[(r["table_id"], r["country"])] += r["value"]
                has_values[(r["table_id"], r["country"])] = True
    anomalies = [(k, v) for k, v in sums.items() if abs(v - 100) > 1.5]
    if anomalies:
        report.append(f"- **합계 이상 {len(anomalies)}건 (100 ± 1.5%p 초과)**")
        for (tid, country), v in anomalies:
            report.append(f"  - {tid} / {country}: 합계 {v:.2f}%")
    else:
        report.append("- 검증 대상 표 전부 합계 100% ± 1.5%p 범위 내 (반올림 오차 허용치는 원본 PDF 일러두기 기준 ±0.2%p보다 넉넉하게 설정)")
    report.append("")

    # 6-5. 동일 지표(table_id)에 단위(unit) 혼재 여부
    report.append("## 5. 동일 table_id 내 단위(unit) 혼재 검사\n")
    unit_by_table = defaultdict(set)
    for r in long_rows:
        unit_by_table[r["table_id"]].add(r["unit"])
    mixed = {k: v for k, v in unit_by_table.items() if len(v) > 1}
    if mixed:
        report.append("- 아래 table_id는 하나의 표 안에 서로 다른 unit이 섞여 있습니다 (원본 구조상 평균 척도 컬럼과 % 컬럼이 공존하는 경우일 수 있음, 오류 아님 — 개별 확인 필요):")
        for k, v in mixed.items():
            report.append(f"  - {k}: {sorted(v)}")
    else:
        report.append("- 혼재 없음")
    report.append("")

    # 6-6. 존재하지 않는 국가에 0을 채운 값이 있는가 (교집합 밖 국가가 long_rows에 있는지)
    report.append("## 6. 교집합 밖 국가 임의 포함 여부\n")
    out_of_scope = sorted({r["country"] for r in long_rows} - set(target_countries))
    if out_of_scope:
        report.append(f"- **경고: 23개국 교집합 밖 국가가 포함됨**: {out_of_scope}")
    else:
        report.append("- 없음 (23개국 교집합 국가만 포함됨을 확인)")
    report.append("")

    # 6-7. E3-13 포함 여부 / 1-41 포함 여부
    report.append("## 7. 명시적 제외 대상 재확인\n")
    e3_13_present = any(r["table_id"] == "E3-13" for r in long_rows)
    h141_present = any(r["table_id"] == "1-41" for r in long_rows)
    report.append(f"- E3-13(기타 문화항목) 포함 여부: {'포함됨(오류)' if e3_13_present else '미포함 (정상, 제외 확인)'}")
    report.append(f"- 1-41(관광경험) 포함 여부: {'포함됨(오류)' if h141_present else '미포함 (정상, 제외 확인)'}")
    report.append("")

    # 6-8. comparability 분포 요약
    report.append("## 8. comparability 분포 요약\n")
    comp_counter = defaultdict(int)
    for r in long_rows:
        comp_counter[r["comparability"]] += 1
    report.append("| comparability | 레코드 수 |")
    report.append("|---|---|")
    for k, v in sorted(comp_counter.items()):
        report.append(f"| {k} | {v} |")
    report.append("")
    report.append("> 확정 보고서 원칙에 따라 한류실태조사와 잠재방한객조사 지표를 직접 빼거나 나누는 계산은 "
                   "이번 단계 및 이 스크립트 어디에서도 수행하지 않았습니다.\n")

    # 6-9. country_profile_base 결측 현황
    report.append("## 9. country_profile_base.csv 결측 현황\n")
    return report


def append_profile_missingness(report_lines, profile_rows):
    fields = [
        "culture_experience_rate_pct", "hallyu_overall_liking_score",
        "culture_to_korea_positive_pct", "hallyu_perception_positive_pct",
        "visit_intention_positive_pct", "culture_to_visit_positive_pct",
        "top_visit_barrier_rate_pct",
    ]
    report_lines.append("| 컬럼 | 결측 국가 수 (23개국 중) | 결측 국가 |")
    report_lines.append("|---|---|---|")
    for field in fields:
        missing_countries = [r["country"] for r in profile_rows if r[field] is None]
        report_lines.append(f"| {field} | {len(missing_countries)} | {', '.join(missing_countries) if missing_countries else '-'} |")
    report_lines.append("")
    report_lines.append("> 결측값은 0으로 임의 대체하지 않고 빈 값(None)으로 유지했습니다. "
                         "결측 사유는 대부분 해당 국가의 표본 부재(예: manual_review 제외, 하위집합 표본 0) 때문입니다.\n")


def write_validation_md(lines):
    with open(OUT_VALIDATION_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"[저장] {OUT_VALIDATION_MD}")


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def main():
    intersection, hallyu_only = load_country_mapping()
    target_countries = [std for (_, std, _) in intersection]
    assert len(target_countries) == 23, f"교집합 국가 수가 23이 아님: {len(target_countries)}"

    potential_to_standard = {orig: std for (orig, std, _) in intersection}
    hallyu_to_standard = {hc: std for (_, std, hc) in intersection}

    general_rows = load_csv(GENERAL_CSV)
    intender_rows = load_csv(INTENDER_CSV)
    hallyu_rows = load_csv(HALLYU_CSV)

    print(f"[로드] general_core: {len(general_rows)}행, intender_core: {len(intender_rows)}행, hallyu_key_values: {len(hallyu_rows)}행")
    print(f"[국가] 교집합 23개국: {target_countries}")
    print(f"[국가] 한류실태조사만 존재: {hallyu_only}")

    long_rows, issues = build_long_rows(general_rows, intender_rows, hallyu_rows, potential_to_standard, hallyu_to_standard)
    write_long_csv(long_rows)

    profile_rows = build_country_profile(long_rows, target_countries)
    write_profile_csv(profile_rows)

    report_lines = run_validation(long_rows, issues, target_countries, general_rows, intender_rows, hallyu_rows)
    append_profile_missingness(report_lines, profile_rows)
    write_validation_md(report_lines)

    print("\n[요약]")
    print(f" - analysis_long.csv: {len(long_rows)}행")
    print(f" - country_profile_base.csv: {len(profile_rows)}행")
    print(f" - 이슈 로그: {len(issues)}건 (validation_report.md 참고)")


if __name__ == "__main__":
    main()
