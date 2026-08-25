# -*- coding: utf-8 -*-
"""
국가별 병목 유형화 규칙 고도화 (Gap/장벽 기반, 규칙 기반, 재현 가능)

입력(읽기 전용, 수정하지 않음):
  - data/processed/gap_analysis.csv                (Direct Gap = E1A-1 - B5B-1, direct_within_survey)
  - data/processed/conditional_gap_analysis.csv     (Conditional Gap = E4-1 - E4-3, conditional)
  - data/processed/barrier_pattern_analysis.csv     (B13-1A 8개 장벽, 방문 비의향자 BASE)
  - data/processed/gap_barrier_correlation.csv      (참고용 — 유형 판정 기준으로 직접 사용하지 않음)
  - data/processed/sensitivity_analysis.csv         (참고용 — 소표본 민감도 서술에 인용)
  - data/processed/country_profile_base.csv

원칙(이번 단계에서 절대 하지 않는 것):
  - 군집분석, 종합점수, 서비스 우선순위 점수
  - 인과관계 주장, 개인 단위 전환 해석
  - 서로 다른 BASE의 직접 차감(이미 계산된 Gap CSV를 그대로 인용만 함)
  - 원본/기존 분석 CSV 수정
  - 임의의 절대 기준값 신규 도입 (모든 판정은 23개국 분포 내 상대적 tercile 사용)

유형 정의(전부 상대적 tercile 기반, 절대 임계값 없음):
  - Type A (direct_gap): Direct Gap이 23개국 중 상위3분위
  - Type B (conditional_gap): Conditional Gap이 23개국 중 상위3분위
  - Type C (인지/관심 장벽): '낮은 한국 인지도' 또는 '한류 관심 부재' 중 하나 이상이 해당 장벽의
    23개국 분포에서 상위3분위
  - Type D (이미지 장벽): '부정적인 한국 이미지'가 상위3분위
  - Type E (경제/물리적 접근성 장벽): '여행경비/물가' 또는 '장거리 비행' 중 하나 이상이 상위3분위
  - Type F (제도/언어 장벽): '비자/출입국 절차' 또는 '불편한 언어소통' 중 하나 이상이 상위3분위
  - Type G (종교/문화환경 장벽): '불편한 종교 환경'이 상위3분위

한 국가는 여러 유형(A~G)에 동시에 속할 수 있다. 장벽 기반 유형(C~G)은 B13-1A(방문 비의향자) BASE이므로
소표본(n<30) 국가는 별도 플래그로 표시하며, 판정 자체를 삭제하지 않는다("가능성 — 소표본 주의").

산출물:
  - data/processed/country_bottleneck_profile.csv
  - data/processed/bottleneck_type_summary.csv
  - data/processed/bottleneck_typology_report.md
"""

from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"

GAP_CSV = PROCESSED_DIR / "gap_analysis.csv"
COND_GAP_CSV = PROCESSED_DIR / "conditional_gap_analysis.csv"
BARRIER_CSV = PROCESSED_DIR / "barrier_pattern_analysis.csv"
CORR_CSV = PROCESSED_DIR / "gap_barrier_correlation.csv"
SENS_CSV = PROCESSED_DIR / "sensitivity_analysis.csv"
PROFILE_CSV = PROCESSED_DIR / "country_profile_base.csv"

OUT_PROFILE_CSV = PROCESSED_DIR / "country_bottleneck_profile.csv"
OUT_SUMMARY_CSV = PROCESSED_DIR / "bottleneck_type_summary.csv"
OUT_REPORT_MD = PROCESSED_DIR / "bottleneck_typology_report.md"

SMALL_SAMPLE_COUNTRIES = {"베트남", "인도네시아", "태국", "필리핀"}

# 기존(잠정) Type A~D — 재검토 대상으로만 인용, 최종 유형 판정에는 사용하지 않음
PRIOR_TYPES = {
    "Type A(직접전환형, 잠정)": ["카자흐스탄", "러시아", "미국", "멕시코", "인도", "태국"],
    "Type B(조건부전환형, 잠정)": ["독일", "호주", "영국"],
    "Type C(인지·이미지형, 잠정)": ["일본", "프랑스", "독일", "러시아"],
    "Type D(물류/접근성형, 잠정)": ["베트남", "태국", "독일", "영국"],
}

# 장벽 그룹 정의(분석 편의를 위한 묶음 — 원본 B13-1A 문항 자체는 변경하지 않음)
BARRIER_GROUPS = {
    "인지관심": ["낮은_한국_인지도", "한류_관심_부재"],
    "이미지": ["부정적_한국_이미지"],
    "경제물리적접근성": ["여행경비_물가", "장거리_비행"],
    "제도언어": ["비자_출입국_절차", "불편한_언어소통"],
    "종교문화환경": ["불편한_종교환경"],
}

TYPE_DEFS = [
    dict(code="Type A", key="direct_gap", label="Direct Gap 상위3분위",
         criterion="Direct Gap(E1A-1-B5B-1)이 23개국 분포에서 상위3분위"),
    dict(code="Type B", key="conditional_gap", label="Conditional Gap 상위3분위",
         criterion="Conditional Gap(E4-1-E4-3)이 23개국 분포에서 상위3분위"),
    dict(code="Type C", key="인지관심", label="인지/관심 장벽",
         criterion="'낮은 한국 인지도' 또는 '한류 관심 부재' 중 하나 이상이 해당 장벽 분포에서 상위3분위"),
    dict(code="Type D", key="이미지", label="이미지 장벽",
         criterion="'부정적인 한국 이미지'가 해당 장벽 분포에서 상위3분위"),
    dict(code="Type E", key="경제물리적접근성", label="경제/물리적 접근성 장벽",
         criterion="'여행경비/물가' 또는 '장거리 비행' 중 하나 이상이 해당 장벽 분포에서 상위3분위"),
    dict(code="Type F", key="제도언어", label="제도/언어 장벽",
         criterion="'비자/출입국 절차' 또는 '불편한 언어소통' 중 하나 이상이 해당 장벽 분포에서 상위3분위"),
    dict(code="Type G", key="종교문화환경", label="종교/문화환경 장벽",
         criterion="'불편한 종교 환경'이 해당 장벽 분포에서 상위3분위"),
]


def load_csv(path):
    with open(path, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def to_float(x):
    if x in (None, ""):
        return None
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def tercile_top_set(values_by_country):
    """23개국 값을 정렬 후 상위3분위에 속하는 국가 집합을 반환한다.
    (기존 단계와 동일한 순서통계량 기반 tercile 방식, 새로운 절대 기준값 없음)"""
    items = sorted(values_by_country.items(), key=lambda kv: kv[1])
    n = len(items)
    cut2 = n - n // 3
    return {c for c, v in items[cut2:]}


def load_all():
    gap_rows = load_csv(GAP_CSV)
    cond_rows = load_csv(COND_GAP_CSV)
    barrier_rows = load_csv(BARRIER_CSV)

    direct_gap = {r["country"]: to_float(r["observed_gap_pct_point"]) for r in gap_rows}
    direct_gap_tier = {r["country"]: r["gap_tier"] for r in gap_rows}
    cond_gap = {r["country"]: to_float(r["observed_conditional_gap_pct_point"]) for r in cond_rows}
    cond_gap_tier = {r["country"]: r["gap_tier"] for r in cond_rows}

    barrier_values = defaultdict(dict)  # barrier_label -> {country: value}
    small_sample_flag = {}
    for r in barrier_rows:
        c = r["country"]
        small_sample_flag[c] = r["small_sample_flag"]
        for label in ("한류_관심_부재", "낮은_한국_인지도", "부정적_한국_이미지", "불편한_언어소통",
                      "여행경비_물가", "비자_출입국_절차", "장거리_비행", "불편한_종교환경"):
            barrier_values[label][c] = to_float(r[label])

    return direct_gap, direct_gap_tier, cond_gap, cond_gap_tier, barrier_values, small_sample_flag


def build_barrier_top_sets(barrier_values):
    """개별 장벽(8개)마다 23개국 분포 기준 상위3분위 국가 집합 계산"""
    top_sets = {}
    for label, values in barrier_values.items():
        top_sets[label] = tercile_top_set(values)
    return top_sets


def build_group_flags(barrier_top_sets, small_sample_flag, countries):
    """그룹별(5개) 국가 -> (flag Y/N, trigger된 세부 장벽 목록, 소표본 주의 여부)"""
    group_flag = {}  # group_key -> {country: dict(flag, triggers, small_sample_caution)}
    for group_key, barriers in BARRIER_GROUPS.items():
        result = {}
        for country in countries:
            triggers = [b for b in barriers if country in barrier_top_sets[b]]
            flag = "Y" if triggers else "N"
            caution = "Y" if (flag == "Y" and small_sample_flag.get(country) == "Y") else "N"
            result[country] = dict(flag=flag, triggers=triggers, small_sample_caution=caution)
        group_flag[group_key] = result
    return group_flag


BARRIER_LABEL_KR = {
    "한류_관심_부재": "한류 관심 부재",
    "낮은_한국_인지도": "낮은 한국 인지도",
    "부정적_한국_이미지": "부정적인 한국 이미지",
    "불편한_언어소통": "불편한 언어소통",
    "여행경비_물가": "여행경비/물가",
    "비자_출입국_절차": "비자/출입국 절차",
    "장거리_비행": "장거리 비행",
    "불편한_종교환경": "불편한 종교 환경",
}


def build_country_profile(direct_gap, direct_gap_tier, cond_gap, cond_gap_tier, group_flag, small_sample_flag):
    countries = sorted(direct_gap.keys())
    rows = []
    type_membership = defaultdict(set)  # type_code -> set(countries)

    for country in countries:
        direct_flag = "Y" if direct_gap_tier.get(country) == "Gap_큼(상위3분위)" else "N"
        cond_flag = "Y" if cond_gap_tier.get(country) == "Gap_큼(상위3분위)" else "N"

        row = dict(
            country=country,
            direct_gap_pct_point=round(direct_gap[country], 2) if direct_gap.get(country) is not None else None,
            direct_gap_type_flag=direct_flag,
            conditional_gap_pct_point=round(cond_gap[country], 2) if cond_gap.get(country) is not None else None,
            conditional_gap_type_flag=cond_flag,
        )

        if direct_flag == "Y":
            type_membership["Type A"].add(country)
        if cond_flag == "Y":
            type_membership["Type B"].add(country)

        group_code_map = {"인지관심": "Type C", "이미지": "Type D", "경제물리적접근성": "Type E",
                           "제도언어": "Type F", "종교문화환경": "Type G"}
        group_colname_map = {"인지관심": "cognition_interest_barrier_flag", "이미지": "image_barrier_flag",
                              "경제물리적접근성": "economic_physical_access_barrier_flag",
                              "제도언어": "institutional_language_barrier_flag",
                              "종교문화환경": "religious_cultural_env_barrier_flag"}

        small_sample_notes = []
        triggered_labels = []  # (type_code, group_label_kr, [barrier_kr...])
        for group_key, colname in group_colname_map.items():
            info = group_flag[group_key][country]
            flag_val = info["flag"]
            if info["small_sample_caution"] == "Y":
                flag_val = "가능성(소표본 주의)"
                small_sample_notes.append(group_key)
            row[colname] = flag_val
            if info["flag"] == "Y":
                type_membership[group_code_map[group_key]].add(country)
                triggered_labels.append((group_code_map[group_key], group_key,
                                          [BARRIER_LABEL_KR[b] for b in info["triggers"]]))

        # 주요 관찰 패턴 텍스트
        pattern_parts = []
        if direct_flag == "Y":
            pattern_parts.append("Type A(Direct Gap 상위3분위)")
        if cond_flag == "Y":
            pattern_parts.append("Type B(Conditional Gap 상위3분위)")
        for code, group_key, kr_labels in triggered_labels:
            label_map = {"Type C": "인지/관심 장벽", "Type D": "이미지 장벽",
                         "Type E": "경제/물리적 접근성 장벽", "Type F": "제도/언어 장벽",
                         "Type G": "종교/문화환경 장벽"}
            pattern_parts.append(f"{code}({label_map[code]}: {', '.join(kr_labels)})")
        row["key_observed_pattern"] = "; ".join(pattern_parts) if pattern_parts else "상위3분위 유형 없음(중/하위권)"

        # 해석 시 주의사항
        caution_parts = [
            "Direct Gap(전체 응답자 BASE)과 Conditional Gap(문화경험자 하위집합 BASE), 장벽 비율(방문 비의향자 하위집합 BASE)은 "
            "서로 다른 BASE에서 계산된 값이므로 하나의 개인 수준 지표로 합산하거나 인과관계로 해석하지 않는다."
        ]
        if small_sample_notes:
            caution_parts.append(
                f"이 국가는 B13-1A 방문 비의향자 표본이 30명 미만(소표본)이므로, 장벽 기반 유형 중 "
                f"{', '.join(small_sample_notes)} 판정은 국가 간 비교의 강한 근거로 사용하지 않는다."
            )
        row["small_sample_barrier_note"] = "Y" if small_sample_notes else "N"
        row["interpretation_caution"] = " ".join(caution_parts)

        rows.append(row)

    return rows, type_membership, countries


def write_profile_csv(rows):
    fieldnames = [
        "country", "direct_gap_pct_point", "direct_gap_type_flag",
        "conditional_gap_pct_point", "conditional_gap_type_flag",
        "cognition_interest_barrier_flag", "image_barrier_flag",
        "economic_physical_access_barrier_flag", "institutional_language_barrier_flag",
        "religious_cultural_env_barrier_flag", "small_sample_barrier_note",
        "key_observed_pattern", "interpretation_caution",
    ]
    with open(OUT_PROFILE_CSV, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    print(f"[저장] {OUT_PROFILE_CSV} ({len(rows)}행)")


# ---------------------------------------------------------------------------
# 유형별 요약 + 중복/구별력 검증
# ---------------------------------------------------------------------------


def build_type_summary(type_membership, countries, barrier_top_sets, direct_gap_tier, cond_gap_tier):
    n_total = len(countries)
    rows = []
    for tdef in TYPE_DEFS:
        code = tdef["code"]
        members = sorted(type_membership.get(code, set()))
        n = len(members)

        other_membership_count = 0
        for c in members:
            other_types = [t["code"] for t in TYPE_DEFS if t["code"] != code and c in type_membership.get(t["code"], set())]
            if other_types:
                other_membership_count += 1

        major_barrier_detail = ""
        if tdef["key"] in BARRIER_GROUPS:
            trig_counts = []
            for b in BARRIER_GROUPS[tdef["key"]]:
                cnt = len(barrier_top_sets[b] & set(members))
                trig_counts.append(f"{BARRIER_LABEL_KR[b]}({cnt}개국)")
            major_barrier_detail = ", ".join(trig_counts)
        elif tdef["key"] == "direct_gap":
            major_barrier_detail = "Direct Gap(E1A-1-B5B-1) 자체 상위3분위 기준"
        elif tdef["key"] == "conditional_gap":
            major_barrier_detail = "Conditional Gap(E4-1-E4-3) 자체 상위3분위 기준"

        gap_consistency_note = ""
        if code == "Type A":
            gap_consistency_note = "정의 자체가 Direct Gap 상위3분위이므로 앞 단계 gap_analysis.csv 결과와 100% 일치"
        elif code == "Type B":
            gap_consistency_note = "정의 자체가 Conditional Gap 상위3분위이므로 앞 단계 conditional_gap_analysis.csv 결과와 100% 일치"
        else:
            overlap_a = len(set(members) & type_membership.get("Type A", set()))
            gap_consistency_note = f"Direct Gap 상위3분위(Type A)와 동시에 속하는 국가: {overlap_a}개국"

        pct = round(100 * n / n_total, 1)
        broad_flag = "Y" if pct >= 65 else "N"

        rows.append(dict(
            type_code=code, type_label=tdef["label"], criterion=tdef["criterion"],
            n_countries=n, pct_of_23=pct, country_list="; ".join(members),
            n_also_in_other_type=other_membership_count, major_barrier_detail=major_barrier_detail,
            prior_gap_consistency_note=gap_consistency_note, overly_broad_flag=broad_flag,
        ))
    return rows


def write_summary_csv(rows):
    fieldnames = ["type_code", "type_label", "criterion", "n_countries", "pct_of_23", "country_list",
                  "n_also_in_other_type", "major_barrier_detail", "prior_gap_consistency_note", "overly_broad_flag"]
    with open(OUT_SUMMARY_CSV, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    print(f"[저장] {OUT_SUMMARY_CSV} ({len(rows)}행)")


# ---------------------------------------------------------------------------
# 보고서
# ---------------------------------------------------------------------------


def build_report_md(profile_rows, summary_rows, type_membership, countries, small_sample_flag):
    lines = []
    lines.append("# 국가별 병목 유형화 규칙 고도화 보고서\n")
    lines.append(
        "이 보고서는 `gap_analysis.csv`, `conditional_gap_analysis.csv`, `barrier_pattern_analysis.csv`, "
        "`gap_barrier_correlation.csv`, `sensitivity_analysis.csv`, `country_profile_base.csv`와 앞 단계 보고서들을 "
        "입력으로 합니다. 이전 단계(`gap_barrier_validation_report.md`)에서 잠정 제시한 Type A~D를 최종안으로 확정하지 "
        "않고, 상대적 tercile 기준(새로운 절대 임계값 없음)으로 국가별 병목 프로파일 규칙을 재정의·검증합니다. "
        "군집분석·종합점수·서비스 우선순위 점수·인과관계 주장·개인 단위 전환 해석·서로 다른 BASE의 직접 차감·원본 수정은 "
        "수행하지 않았습니다. 이 단계는 전략 연결 이전의 **국가별 병목 프로파일 확정 단계**로 취급합니다.\n"
    )

    lines.append("## 1. 기존 Type A~D 재검토\n")
    lines.append("이전 단계(`gap_barrier_validation_report.md` 5절)에서 잠정 제시했던 유형과 소속 국가는 다음과 같습니다.\n")
    lines.append("| 잠정 유형 | 소속 국가 | 재검토 결과 |")
    lines.append("|---|---|---|")
    lines.append(f"| Type A(직접전환형, 잠정) | {', '.join(PRIOR_TYPES['Type A(직접전환형, 잠정)'])} | "
                  f"'Direct Gap 상위3분위 + 임의로 선택한 한 장벽(한류 관심 부재)'을 동시에 만족하는 국가만 나열한 것으로, "
                  f"엄밀한 tercile 규칙이 아니라 서술적 예시였음 → 이번 단계 Type A로 재정의(장벽 조건 제거, Direct Gap만 기준)")
    lines.append(f"| Type B(조건부전환형, 잠정) | {', '.join(PRIOR_TYPES['Type B(조건부전환형, 잠정)'])} | "
                  f"'Conditional Gap 상위3분위이나 Direct Gap은 중/하위'라는 배타 조건이 있어 복수 유형을 허용하지 않았음 "
                  f"→ 이번 단계 Type B로 재정의(Direct Gap 상태와 무관하게 Conditional Gap만 기준, 복수 유형 허용)")
    lines.append(f"| Type C(인지·이미지형, 잠정) | {', '.join(PRIOR_TYPES['Type C(인지·이미지형, 잠정)'])} | "
                  f"'인지'와 '이미지'가 하나로 묶여 있었음 → 이번 단계에서 Type C(인지/관심)와 Type D(이미지)로 분리")
    lines.append(f"| Type D(물류/접근성형, 잠정) | {', '.join(PRIOR_TYPES['Type D(물류/접근성형, 잠정)'])} | "
                  f"'장거리 비행'과 '비자/출입국'을 하나로 묶었으나 성격이 다름(물리적 이동 vs 제도) "
                  f"→ 이번 단계에서 Type E(경제/물리적 접근성: 여행경비·장거리비행)와 Type F(제도/언어: 비자·언어)로 분리\n")

    lines.append("## 2. 유형 판정 기준 (전부 상대적 tercile, 새 절대 기준값 없음)\n")
    lines.append("| 유형 | 라벨 | 판정 기준 |")
    lines.append("|---|---|---|")
    for t in TYPE_DEFS:
        lines.append(f"| {t['code']} | {t['label']} | {t['criterion']} |")
    lines.append(
        "\nType A/B는 이미 계산되어 있는 `gap_analysis.csv` / `conditional_gap_analysis.csv`의 `gap_tier` 컬럼을 "
        "그대로 인용합니다(재계산하지 않음). Type C~G는 8개 장벽 각각에 대해 `barrier_pattern_analysis.csv`의 값을 "
        "23개국 기준으로 다시 tercile 구간화한 뒤, 그룹 내 장벽 중 하나 이상이 상위3분위이면 해당 그룹 유형을 충족한 것으로 "
        "판정합니다(OR 조건).\n"
    )

    lines.append("## 3~4. 복수 유형 허용 + 장벽 그룹 세분화\n")
    lines.append("장벽 그룹(분석 편의를 위한 묶음, 원본 B13-1A 문항 자체는 변경하지 않음):\n")
    for group_key, barriers in BARRIER_GROUPS.items():
        kr = [BARRIER_LABEL_KR[b] for b in barriers]
        lines.append(f"- {group_key}: {', '.join(kr)}")
    lines.append(
        "\n한 국가는 Type A~G 중 여러 유형에 동시에 속할 수 있습니다. 아래 5절 프로파일 표의 "
        "`key_observed_pattern` 컬럼에 국가별로 충족한 유형을 모두 나열했습니다.\n"
    )

    lines.append("## 5. 국가별 최종 병목 프로파일\n")
    lines.append("전체 데이터는 `country_bottleneck_profile.csv` 참조. 아래는 요약 표입니다.\n")
    lines.append("| country | Direct Gap(%p) | A | Cond Gap(%p) | B | C(인지/관심) | D(이미지) | E(경제/접근성) | F(제도/언어) | G(종교/문화) | 소표본주의 |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|---|")
    for r in sorted(profile_rows, key=lambda r: r["country"]):
        lines.append(
            f"| {r['country']} | {r['direct_gap_pct_point']} | {r['direct_gap_type_flag']} | "
            f"{r['conditional_gap_pct_point']} | {r['conditional_gap_type_flag']} | "
            f"{r['cognition_interest_barrier_flag']} | {r['image_barrier_flag']} | "
            f"{r['economic_physical_access_barrier_flag']} | {r['institutional_language_barrier_flag']} | "
            f"{r['religious_cultural_env_barrier_flag']} | {r['small_sample_barrier_note']} |"
        )
    lines.append("")

    lines.append("## 6. 소표본 국가 처리\n")
    lines.append(
        f"B13-1A 방문 비의향자 표본이 30명 미만인 국가: {', '.join(sorted(SMALL_SAMPLE_COUNTRIES))}. "
        f"이 국가들이 장벽 기반 유형(C~G) 조건을 충족하는 경우, 해당 셀에 'Y' 대신 '가능성(소표본 주의)'로 표시했습니다 "
        f"(`country_bottleneck_profile.csv`의 그룹 flag 컬럼 참조). Direct Gap(Type A)과 Conditional Gap(Type B)은 "
        f"B13-1A와 무관한 별도 BASE(전체 응답자 / 문화경험자)이므로 이 소표본 이슈의 영향을 받지 않습니다.\n"
    )

    lines.append("## 7. 유형 검증\n")
    lines.append("| 유형 | 국가 수(23개국 중) | 비율 | 다른 유형과 중복된 국가 수 | 과도하게 넓음(≥65%) |")
    lines.append("|---|---|---|---|---|")
    for r in summary_rows:
        lines.append(f"| {r['type_code']}({r['type_label']}) | {r['n_countries']} | {r['pct_of_23']}% | "
                      f"{r['n_also_in_other_type']} | {r['overly_broad_flag']} |")
    lines.append("")

    broad_types = [r for r in summary_rows if r["overly_broad_flag"] == "Y"]
    lines.append("**[데이터상 나타나는 패턴]**")
    if broad_types:
        names = ", ".join(f"{r['type_code']}({r['pct_of_23']}%)" for r in broad_types)
        lines.append(f"- 23개국의 65% 이상을 포함하는 유형: {names}. 이런 유형은 '상위3분위'라는 정의상 이론적으로는 "
                     f"약 33%(8개국 내외)를 넘지 않아야 하지만, OR 조건으로 2개 장벽을 묶은 그룹(C/E/F)은 두 장벽의 "
                     f"상위3분위 국가 집합이 서로 다르면 합집합이 33%를 넘을 수 있습니다. 이 경우 해당 유형은 "
                     f"'장벽 하나라도 상대적으로 높은 국가'를 넓게 포괄하는 것으로 해석해야 하며, 국가를 세밀하게 "
                     f"구별하는 용도로는 한계가 있습니다.")
    else:
        lines.append("- 65% 이상을 포함하는 과도하게 넓은 유형은 관찰되지 않았습니다.")
    high_overlap = [r for r in summary_rows if r["n_countries"] > 0 and r["n_also_in_other_type"] / r["n_countries"] >= 0.7]
    if high_overlap:
        names = ", ".join(r["type_code"] for r in high_overlap)
        lines.append(f"- 소속 국가의 70% 이상이 다른 유형과도 겹치는 유형: {names}. 이는 해당 유형이 단독으로는 "
                     f"국가를 구별하지 못하고, 다른 유형과 결합해서만 국가별 차이를 드러낸다는 것을 시사합니다.")
    lines.append("")

    lines.append("## 8. 마지막 정리\n")

    a_members = type_membership.get("Type A", set())
    b_members = type_membership.get("Type B", set())
    always_upper_barrier = None
    for t in TYPE_DEFS[2:]:
        members = type_membership.get(t["code"], set())
        if a_members and members and a_members.issubset(members):
            always_upper_barrier = t
            break

    lines.append("### 1) 현재 데이터만으로 확정적으로 말할 수 있는 국가별 패턴")
    lines.append(
        f"- Direct Gap 상위3분위(Type A) 국가: {', '.join(sorted(a_members))} — 이는 `gap_analysis.csv`에 이미 "
        f"계산되어 있는 값의 재인용이므로 '확정적'으로 서술 가능합니다(단, 개인 전환 해석은 여전히 불가)."
    )
    lines.append(
        f"- Conditional Gap 상위3분위(Type B) 국가: {', '.join(sorted(b_members))} — 마찬가지로 재인용값입니다.\n"
    )

    lines.append("### 2) '가능성' 수준으로만 말할 수 있는 패턴")
    lines.append(
        "- Type C~G(장벽 기반 유형) 전체 — 방문 비의향자라는 하위집단 BASE에서 계산된 값이므로, 이 유형에 속한다는 것이 "
        "'해당 국가 전체 여행객의 특성'을 의미하지 않습니다. '~한 장벽이 상대적으로 두드러지는 방문 비의향자 하위집단이 "
        "관찰된다' 수준으로만 서술 가능합니다."
    )
    lines.append(
        "- Type A/B와 Type C~G의 동시 충족(예: `key_observed_pattern`에 여러 유형이 함께 표시된 국가) — 두 값이 "
        "서로 다른 BASE·다른 문항에서 나왔으므로 '이 장벽이 이 Gap의 원인'이라고 말할 수 없고, '함께 관찰된다'까지만 "
        "말할 수 있습니다.\n"
    )

    lines.append("### 3) 유형화가 잘 작동하지 않는 국가")
    no_type_countries = [r["country"] for r in profile_rows if r["key_observed_pattern"] == "상위3분위 유형 없음(중/하위권)"]
    many_type_countries = []
    for r in profile_rows:
        n_types = r["key_observed_pattern"].count(";") + 1 if r["key_observed_pattern"] != "상위3분위 유형 없음(중/하위권)" else 0
        if n_types >= 4:
            many_type_countries.append((r["country"], n_types))
    lines.append(f"- 상위3분위 유형이 하나도 없는 국가(중/하위권에 고르게 위치): {', '.join(no_type_countries) if no_type_countries else '없음'} "
                 f"— 이 국가들은 이번 규칙 체계로는 병목 프로파일을 구별하지 못합니다.")
    if many_type_countries:
        names = ", ".join(f"{c}({n}개 유형)" for c, n in many_type_countries)
        lines.append(f"- 4개 이상의 유형에 동시에 속하는 국가: {names} — 유형이 지나치게 많이 겹쳐 '이 국가의 핵심 병목은 "
                     f"무엇인가'라는 질문에 이 규칙 체계만으로는 단일하게 답하기 어렵습니다.")
    lines.append("")

    lines.append("### 4) 소표본 때문에 보류해야 하는 국가")
    lines.append(
        f"- {', '.join(sorted(SMALL_SAMPLE_COUNTRIES))}: 장벽 기반 유형(C~G) 판정에 '가능성(소표본 주의)' 표시가 "
        f"붙은 경우, 다른 국가와 나란히 비교하는 근거로 사용하지 않아야 합니다. Type A/B(Gap 기반) 판정은 이 소표본 "
        f"이슈와 무관하므로 그대로 사용 가능합니다.\n"
    )

    lines.append("### 5) 다음 단계에서 추가 데이터가 필요한 부분")
    lines.append("- 장벽 응답과 Gap이 동일 응답자에게서 수집된 것이 아니므로, 개인 단위로 두 값을 연결할 수 있는 조사 설계(또는 원자료)가 필요합니다.")
    lines.append("- 소표본 4개국의 B13 표본을 확대하거나, 최소한 해당 국가에서 추가 표본을 확보해야 장벽 기반 유형 판정의 신뢰도를 높일 수 있습니다.")
    lines.append("- Type C/E/F처럼 OR 조건으로 넓게 정의된 유형은, 장벽별로 유형을 더 세분화(예: 인지 vs 관심을 별도 유형으로)할지 여부를 판단하려면 추가 표본이나 문항이 필요합니다.")
    lines.append("- 병목 프로파일과 실제 방한 여부(사후 행동 데이터)를 연결할 수 있는 별도 종단 데이터가 있다면, 이번 규칙 기반 유형의 타당성을 간접적으로 확인할 수 있습니다.\n")

    lines.append("### 6) 서비스/UX 전략으로 연결하기 전에 추가로 검증해야 할 사항")
    lines.append("- 이번 유형은 상관·통계검정 없이 tercile 기준으로만 정의되었으므로, 유형 간 차이가 우연 수준을 넘는지 확인이 필요합니다.")
    lines.append("- 7절에서 과도하게 넓다고 표시된 유형은, 전략 우선순위를 정하는 데 그대로 쓰기에는 구별력이 부족할 수 있습니다.")
    lines.append("- 장벽 유형(C~G)은 방문 비의향자 BASE이므로, 이를 '방문 촉진 전략의 대상'으로 바로 연결하려면 방문 비의향자와 "
                 "실제 잠재 방한객 전체 사이의 관계를 먼저 검증해야 합니다.")
    lines.append("- 소표본 4개국은 전략 우선순위 논의에 포함하기 전에 표본을 보강하거나 별도 취급 방침을 정해야 합니다.")
    lines.append("- 이 보고서는 병목 '프로파일'을 정리한 것이며, 어떤 국가/장벽에 자원을 우선 투입해야 하는지에 대한 "
                 "우선순위나 점수는 계산하지 않았습니다 — 그런 판단이 필요하다면 별도 단계로 설계해야 합니다.\n")

    return lines


def write_report_md(lines):
    with open(OUT_REPORT_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"[저장] {OUT_REPORT_MD}")


def main():
    direct_gap, direct_gap_tier, cond_gap, cond_gap_tier, barrier_values, small_sample_flag = load_all()
    print(f"[로드] direct_gap={len(direct_gap)}개국, cond_gap={len(cond_gap)}개국")
    assert len(direct_gap) == 23 and len(cond_gap) == 23

    barrier_top_sets = build_barrier_top_sets(barrier_values)
    countries = sorted(direct_gap.keys())
    group_flag = build_group_flags(barrier_top_sets, small_sample_flag, countries)

    profile_rows, type_membership, countries = build_country_profile(
        direct_gap, direct_gap_tier, cond_gap, cond_gap_tier, group_flag, small_sample_flag
    )
    write_profile_csv(profile_rows)

    summary_rows = build_type_summary(type_membership, countries, barrier_top_sets, direct_gap_tier, cond_gap_tier)
    write_summary_csv(summary_rows)

    report_lines = build_report_md(profile_rows, summary_rows, type_membership, countries, small_sample_flag)
    write_report_md(report_lines)

    print("\n[요약]")
    for r in summary_rows:
        print(f" - {r['type_code']}({r['type_label']}): {r['n_countries']}개국 ({r['pct_of_23']}%)")


if __name__ == "__main__":
    main()
