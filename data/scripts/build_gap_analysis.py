# -*- coding: utf-8 -*-
"""
동일 BASE 기반 Gap 검증 및 조건부 전환 구간 분석

입력(읽기 전용, 수정하지 않음):
  - data/processed/analysis_long.csv
  - data/processed/country_profile_base.csv

원칙(이번 단계에서 절대 하지 않는 것):
  - E1A-1 -> E4-1 -> E4-3 -> B5B-1 을 하나의 개인 수준 funnel/전환율로 계산하지 않는다.
  - 서로 다른 BASE(1-35 등)를 가진 값끼리 직접 차감하지 않는다.
  - 상관/회귀/군집분석, 종합점수, 서비스 우선순위 점수를 계산하지 않는다.
  - 통계적 유의성을 검증하지 않았으므로 "유의하다/영향을 준다/원인이다/전환율이다" 등의 표현을 쓰지 않는다.

이번 단계에서 하는 것:
  1. E1A-1(문화경험률) - B5B-1(방한의향률) : 동일 BASE(전체 응답자)를 공유하는 유일한 핵심 지표쌍의
     "관찰 Gap"(단순 차감)을 계산한다. 개인 단위 전환 손실/인과관계로 해석하지 않는다.
  2. E4-1(문화->호감도) - E4-3(문화->방문의향) : 동일 BASE(문화경험자 하위집합)를 공유하는 별도의
     "조건부 관찰 Gap"을 계산한다. 1.의 Gap과는 별개 분석축으로 유지한다.
  3. 1-35(한류실태조사)는 모집단/BASE가 다르므로 Gap 계산에서 제외하고 참고 정보로만 유지한다.
  4. B13-1A(방문 비의향자) 안에서 8개 주요 장벽의 국가별 비율을 정리하고, 30명 미만 표본은 표시한다.

산출물:
  - data/processed/gap_analysis.csv
  - data/processed/conditional_gap_analysis.csv
  - data/processed/barrier_pattern_analysis.csv
  - data/processed/gap_validation_report.md
"""

from __future__ import annotations

import csv
import statistics
from collections import defaultdict
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"

LONG_CSV = PROCESSED_DIR / "analysis_long.csv"
PROFILE_CSV = PROCESSED_DIR / "country_profile_base.csv"

OUT_GAP_CSV = PROCESSED_DIR / "gap_analysis.csv"
OUT_COND_GAP_CSV = PROCESSED_DIR / "conditional_gap_analysis.csv"
OUT_BARRIER_CSV = PROCESSED_DIR / "barrier_pattern_analysis.csv"
OUT_REPORT_MD = PROCESSED_DIR / "gap_validation_report.md"

AGGREGATE_MARKERS = {"계", "종합", "종합/Top2", "Top2"}
SMALL_SAMPLE_THRESHOLD = 30

# 4절에서 확인해야 할 8개 주요 장벽 (analysis_long.csv의 response_option과 정확히 일치, 원문 그대로 사용)
BARRIER_KEYWORDS = {
    "한류_관심_부재": "한류(한국 문화 콘텐츠) 문화 관련 관심 부재",
    "낮은_한국_인지도": "여행목적지로서 낮은 한국 인지도",
    "부정적_한국_이미지": "부정적인 한국 관련 이미지",
    "불편한_언어소통": "불편한 언어소통",
    "여행경비_물가": "적당하지 않은 여행경비 및 물가",
    "비자_출입국_절차": "불편한 비자 발급 및 출입국 절차(K-ETA 등)",
    "장거리_비행": "먼 이동거리(장거리 비행 필요)",
    "불편한_종교환경": "불편한 종교 환경(음식, 기도실 등)",
}

# 이번 단계 관찰 대상 3개국 (앞 단계 direct_within_survey 병목 가능성 관찰 국가, 정의 변경 없이 그대로 인용)
PRIOR_OBSERVED_COUNTRIES = ["러시아", "인도", "카자흐스탄"]


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


def gap_tier_labels(values_by_country):
    """Gap 값을 정렬 후 3분위(작음/중간/큼)로 구간화한다.
    이는 순위나 종합점수가 아니라 순서통계량 기반의 상대적 위치 기술이다."""
    items = sorted(values_by_country.items(), key=lambda kv: kv[1])
    n = len(items)
    cut1 = n // 3
    cut2 = n - n // 3
    labels = {}
    for i, (country, val) in enumerate(items):
        if i < cut1:
            labels[country] = "Gap_작음(하위3분위)"
        elif i < cut2:
            labels[country] = "Gap_중간(중위3분위)"
        else:
            labels[country] = "Gap_큼(상위3분위)"
    return labels


# ---------------------------------------------------------------------------
# 1. E1A-1 <-> B5B-1 동일 BASE Gap
# ---------------------------------------------------------------------------


def build_gap_analysis(profile_rows):
    rows = []
    values = {}
    for r in profile_rows:
        country = r["country"]
        exp = to_float(r["culture_experience_rate_pct"])
        vis = to_float(r["visit_intention_positive_pct"])
        if exp is None or vis is None:
            continue
        gap = exp - vis
        values[country] = gap
        rows.append(dict(
            country=country,
            culture_experience_rate_pct=round(exp, 2),
            visit_intention_positive_pct=round(vis, 2),
            observed_gap_pct_point=round(gap, 2),
            base_type="전체 응답자(잠재방한객조사 일반외국인, n=16,360)",
            comparability="direct_within_survey",
        ))

    tiers = gap_tier_labels(values)
    for r in rows:
        r["gap_tier"] = tiers[r["country"]]

    gap_values = list(values.values())
    stats = dict(
        n=len(gap_values),
        min=round(min(gap_values), 2),
        q1=round(statistics.quantiles(gap_values, n=4)[0], 2),
        median=round(statistics.median(gap_values), 2),
        q3=round(statistics.quantiles(gap_values, n=4)[2], 2),
        max=round(max(gap_values), 2),
        mean=round(statistics.mean(gap_values), 2),
        stdev=round(statistics.pstdev(gap_values), 2),
    )
    return sorted(rows, key=lambda r: -r["observed_gap_pct_point"]), stats


def write_gap_csv(rows):
    fieldnames = ["country", "culture_experience_rate_pct", "visit_intention_positive_pct",
                  "observed_gap_pct_point", "gap_tier", "base_type", "comparability"]
    with open(OUT_GAP_CSV, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    print(f"[저장] {OUT_GAP_CSV} ({len(rows)}행)")


# ---------------------------------------------------------------------------
# 2. E4-1 <-> E4-3 조건부 Gap (문화경험자 하위집합 내부, 1.과 별개 분석축)
# ---------------------------------------------------------------------------


def build_conditional_gap_analysis(profile_rows):
    rows = []
    values = {}
    for r in profile_rows:
        country = r["country"]
        e41 = to_float(r["culture_to_korea_positive_pct"])
        e43 = to_float(r["culture_to_visit_positive_pct"])
        if e41 is None or e43 is None:
            continue
        gap = e41 - e43
        values[country] = gap
        rows.append(dict(
            country=country,
            culture_to_korea_positive_pct=round(e41, 2),
            culture_to_visit_positive_pct=round(e43, 2),
            observed_conditional_gap_pct_point=round(gap, 2),
            base_type="문화경험자(잠재방한객조사, 전체 응답자의 하위집합)",
            comparability="conditional",
        ))

    tiers = gap_tier_labels(values)
    for r in rows:
        r["gap_tier"] = tiers[r["country"]]

    gap_values = list(values.values())
    stats = dict(
        n=len(gap_values),
        min=round(min(gap_values), 2),
        q1=round(statistics.quantiles(gap_values, n=4)[0], 2),
        median=round(statistics.median(gap_values), 2),
        q3=round(statistics.quantiles(gap_values, n=4)[2], 2),
        max=round(max(gap_values), 2),
        mean=round(statistics.mean(gap_values), 2),
        stdev=round(statistics.pstdev(gap_values), 2),
    )
    return sorted(rows, key=lambda r: -r["observed_conditional_gap_pct_point"]), stats


def write_cond_gap_csv(rows):
    fieldnames = ["country", "culture_to_korea_positive_pct", "culture_to_visit_positive_pct",
                  "observed_conditional_gap_pct_point", "gap_tier", "base_type", "comparability"]
    with open(OUT_COND_GAP_CSV, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    print(f"[저장] {OUT_COND_GAP_CSV} ({len(rows)}행)")


# ---------------------------------------------------------------------------
# 3. B13-1A 8개 주요 장벽 국가별 비율 + 소표본 표시
# ---------------------------------------------------------------------------


def build_barrier_pattern(long_rows, table_id="B13-1A"):
    # country -> sample_n (해당 table_id, base=방문 비의향자 표본 크기; 동일 국가 내 여러 row가 같은 sample_n을 반복하므로 첫 값 사용)
    sample_n_by_country = {}
    value_by_country_barrier = defaultdict(dict)

    for r in long_rows:
        if r["table_id"] != table_id:
            continue
        if r["response_option"] in AGGREGATE_MARKERS:
            continue
        country = r["country"]
        opt = r["response_option"]
        val = to_float(r["value"])
        n = to_float(r["sample_n"])
        if n is not None:
            sample_n_by_country[country] = n
        for label, keyword in BARRIER_KEYWORDS.items():
            if opt == keyword and val is not None:
                value_by_country_barrier[country][label] = val

    rows = []
    for country in sorted(value_by_country_barrier):
        n = sample_n_by_country.get(country)
        small_sample_flag = "Y" if (n is not None and n < SMALL_SAMPLE_THRESHOLD) else "N"
        row = dict(
            country=country,
            base_type="방문 비의향자(B13-1A, 잠재방한객조사)",
            sample_n=n,
            small_sample_flag=small_sample_flag,
        )
        for label in BARRIER_KEYWORDS:
            row[label] = value_by_country_barrier[country].get(label)
        rows.append(row)
    return rows


def write_barrier_csv(rows):
    fieldnames = ["country", "base_type", "sample_n", "small_sample_flag"] + list(BARRIER_KEYWORDS.keys())
    with open(OUT_BARRIER_CSV, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    print(f"[저장] {OUT_BARRIER_CSV} ({len(rows)}행)")


# ---------------------------------------------------------------------------
# 보고서
# ---------------------------------------------------------------------------


def build_report_md(gap_rows, gap_stats, cond_rows, cond_stats, barrier_rows):
    lines = []
    lines.append("# 동일 BASE 기반 Gap 검증 및 조건부 전환 구간 분석 보고서\n")
    lines.append(
        "이 보고서는 `analysis_long.csv`, `country_profile_base.csv`를 입력으로 하며, "
        "앞 단계(`country_pattern_analysis_report.md`)에서 tercile 기반으로 관찰된 병목 가능성이 "
        "실제 수치 차이(Gap)에서도 나타나는지 검증합니다. "
        "여기서 'Gap'은 **동일 BASE를 공유하는 두 지표 사이의 단순 차감(관찰값)**만을 의미하며, "
        "개인 단위의 실제 전환 손실이나 인과관계, 통계적 유의성을 의미하지 않습니다. "
        "상관/회귀/군집분석, 종합점수, 서비스 우선순위 점수는 수행하지 않았습니다.\n"
    )

    lines.append("## 결과를 구분하는 3개 수준")
    lines.append("이 보고서의 모든 서술은 다음 세 수준을 명시적으로 구분합니다.")
    lines.append("- **[관찰된 수치 차이]**: CSV에 그대로 계산되어 있는 값 (Gap, 비율 등)")
    lines.append("- **[패턴으로 관찰되는 국가 특성]**: 여러 관찰된 수치를 나열했을 때 눈에 띄는 공통점 (통계적 검정 없음)")
    lines.append("- **[추가 검증이 필요한 해석/가설]**: 다음 단계에서 통계적으로 확인해야 하는 가설 (아직 사실로 확정되지 않음)\n")

    # 1. E1A-1 <-> B5B-1 Gap
    lines.append("## 1. E1A-1(문화경험률) ↔ B5B-1(방한의향률) Gap\n")
    lines.append(
        "**[관찰된 수치 차이]** 두 지표는 잠재방한객조사(일반외국인) 전체 응답자(n=16,360)라는 동일 BASE를 공유하므로 "
        "`관찰 Gap = 문화경험률(%) - 방한의향률(%)`을 계산했습니다. 이 값은 percentage-point 단위의 단순 차감이며, "
        "개인이 문화를 경험한 뒤 방문 의향으로 '전환되지 못한 비율'을 의미하지 않습니다(서로 다른 응답자일 수 있음).\n"
    )
    lines.append("### Gap의 국가별 분포")
    lines.append(f"- n={gap_stats['n']}, min={gap_stats['min']}, q1={gap_stats['q1']}, median={gap_stats['median']}, "
                  f"q3={gap_stats['q3']}, max={gap_stats['max']}, mean={gap_stats['mean']}, stdev={gap_stats['stdev']}")
    lines.append("")
    lines.append("| country | 문화경험률(E1A-1) | 방한의향률(B5B-1) | 관찰 Gap(%p) | Gap 구간 |")
    lines.append("|---|---|---|---|---|")
    for r in gap_rows:
        lines.append(f"| {r['country']} | {r['culture_experience_rate_pct']} | {r['visit_intention_positive_pct']} | "
                      f"{r['observed_gap_pct_point']} | {r['gap_tier']} |")
    lines.append("")

    prior_gap = {r["country"]: r for r in gap_rows if r["country"] in PRIOR_OBSERVED_COUNTRIES}
    big_gap_tier_countries = [r["country"] for r in gap_rows if r["gap_tier"] == "Gap_큼(상위3분위)"]
    lines.append("### 앞 단계 관찰(러시아·인도·카자흐스탄)과의 대조\n")
    lines.append("**[관찰된 수치 차이]**")
    for c in PRIOR_OBSERVED_COUNTRIES:
        r = prior_gap.get(c)
        if r:
            lines.append(f"- {c}: 관찰 Gap = {r['observed_gap_pct_point']}%p ({r['gap_tier']})")
    matched = [c for c in PRIOR_OBSERVED_COUNTRIES if prior_gap.get(c, {}).get("gap_tier") == "Gap_큼(상위3분위)"]
    not_matched = [c for c in PRIOR_OBSERVED_COUNTRIES if c not in matched]
    lines.append("")
    lines.append("**[패턴으로 관찰되는 국가 특성]**")
    if matched:
        lines.append(f"- {', '.join(matched)}은(는) Gap 구간 분류에서도 '상위3분위(Gap 큼)'에 속해, 앞 단계의 tercile 기반 "
                      f"'Layer1→Layer3 구간 하락' 관찰과 방향이 일치합니다.")
    if not_matched:
        lines.append(f"- {', '.join(not_matched)}는 앞 단계에서 tier 하락이 관찰되었으나, 이번 Gap 구간 분류에서는 "
                      f"'상위3분위(Gap 큼)'에 속하지 않아 두 관찰 방식(tercile vs 단순 차감)의 결과가 완전히 일치하지는 않습니다.")
    lines.append(f"- Gap이 '상위3분위(Gap 큼)'로 분류된 전체 국가는 {', '.join(big_gap_tier_countries)}이며, "
                  f"이는 러시아·인도·카자흐스탄 3개국에 한정되지 않습니다.\n")

    # 2. E4-1 <-> E4-3 조건부 Gap
    lines.append("## 2. E4-1(문화→호감도) ↔ E4-3(문화→방문의향) 조건부 Gap\n")
    lines.append(
        "**[관찰된 수치 차이]** 두 지표는 잠재방한객조사의 '문화경험자'라는 동일 하위집합을 BASE로 공유하므로 "
        "`관찰 조건부 Gap = 문화→호감도 긍정률(%) - 문화→방문의향 긍정률(%)`을 계산했습니다. "
        "이 값은 1절의 Gap과 **별개의 분석축**이며, E1A-1→E4-1→E4-3→B5B-1을 하나의 funnel로 합치지 않았습니다.\n"
    )
    lines.append("### 조건부 Gap의 국가별 분포")
    lines.append(f"- n={cond_stats['n']}, min={cond_stats['min']}, q1={cond_stats['q1']}, median={cond_stats['median']}, "
                  f"q3={cond_stats['q3']}, max={cond_stats['max']}, mean={cond_stats['mean']}, stdev={cond_stats['stdev']}")
    lines.append("")
    lines.append("| country | 문화→호감도(E4-1) | 문화→방문의향(E4-3) | 관찰 조건부 Gap(%p) | Gap 구간 |")
    lines.append("|---|---|---|---|---|")
    for r in cond_rows:
        lines.append(f"| {r['country']} | {r['culture_to_korea_positive_pct']} | {r['culture_to_visit_positive_pct']} | "
                      f"{r['observed_conditional_gap_pct_point']} | {r['gap_tier']} |")
    lines.append("")

    cond_big = [r["country"] for r in cond_rows if r["gap_tier"] == "Gap_큼(상위3분위)"]
    lines.append("**[패턴으로 관찰되는 국가 특성]**")
    lines.append(f"- 조건부 Gap이 '상위3분위(Gap 큼)'로 분류된 국가: {', '.join(cond_big)}\n")

    # 3. 1-35 제외 사유
    lines.append("## 3. 1-35(한류실태 인식긍정률) Gap 계산 제외\n")
    lines.append(
        "**[관찰된 수치 차이]** 해당 없음 — 1-35(한류실태조사)는 잠재방한객조사와 모집단이 다른 별도 패널(한류 경험자 전용)이므로 "
        "E4-1 또는 다른 지표와 직접 차감하지 않았습니다. 앞 단계 보고서와 동일하게, 국가별 프로파일의 참고 정보로만 유지합니다 "
        "(`country_pattern_profile.csv`의 `hallyu_perception_positive_pct` 컬럼 참조).\n"
    )

    # 4. 장벽 분석
    lines.append("## 4. B13-1A 방문 비의향자 BASE 내 주요 장벽 국가별 분포\n")
    lines.append(
        "**[관찰된 수치 차이]** 아래 비율은 모두 '방문 비의향자'라는 하위집단 안에서의 응답 비율이며, "
        "해당 국가 전체 인구의 비율이 아닙니다. `small_sample_flag=Y`인 국가/조건은 방문 비의향자 표본이 30명 미만으로, "
        "국가 간 비교의 강한 근거로 사용하지 않습니다.\n"
    )
    header = "| country | 표본n | 소표본 | " + " | ".join(BARRIER_KEYWORDS.keys()) + " |"
    sep = "|---|---|---|" + "---|" * len(BARRIER_KEYWORDS)
    lines.append(header)
    lines.append(sep)
    for r in barrier_rows:
        cells = []
        for label in BARRIER_KEYWORDS:
            v = r.get(label)
            cells.append(f"{v:.1f}" if v is not None else "-")
        n_display = f"{int(r['sample_n'])}" if r["sample_n"] is not None else "-"
        lines.append(f"| {r['country']} | {n_display} | {r['small_sample_flag']} | " + " | ".join(cells) + " |")
    lines.append("")

    small_sample_countries = [r["country"] for r in barrier_rows if r["small_sample_flag"] == "Y"]
    lines.append("**[관찰된 수치 차이]**")
    lines.append(f"- 방문 비의향자 표본이 30명 미만인 국가: {', '.join(small_sample_countries) if small_sample_countries else '없음'}\n")

    lines.append("**[패턴으로 관찰되는 국가 특성]**")
    hallyu_barrier_countries = [r["country"] for r in barrier_rows if (r.get("한류_관심_부재") or 0) >= 20]
    lines.append(f"- '한류 관심 부재' 장벽 비율이 20% 이상인 국가: {', '.join(hallyu_barrier_countries)}")
    lang_barrier_countries = [r["country"] for r in barrier_rows if (r.get("불편한_언어소통") or 0) >= 30]
    lines.append(f"- '불편한 언어소통' 장벽 비율이 30% 이상인 국가: {', '.join(lang_barrier_countries)}")
    lines.append("")

    # Gap x 장벽 교차 관찰
    barrier_by_country = {r["country"]: r for r in barrier_rows}
    gap_by_country = {r["country"]: r for r in gap_rows}
    both_gap_and_barrier = []
    for c in big_gap_tier_countries:
        b = barrier_by_country.get(c)
        if b and (b.get("한류_관심_부재") or 0) >= 15:
            both_gap_and_barrier.append(c)
    lines.append("**[추가 검증이 필요한 해석/가설]**")
    lines.append(
        f"- Gap이 '상위3분위(Gap 큼)'로 분류되면서 동시에 '한류 관심 부재' 장벽 비율도 상대적으로 높게(15% 이상) 나타난 국가: "
        f"{', '.join(both_gap_and_barrier) if both_gap_and_barrier else '없음'}. "
        f"이 국가들에서 '문화경험률은 높으나 방한의향은 낮고, 그 이유의 일부로 한류 관심 부재가 언급된다'는 패턴이 "
        f"동시에 나타나지만, 두 지표는 서로 다른 문항·다른 하위집단(B13-1A는 방문 비의향자만)에서 수집된 값이므로 "
        f"이 둘 사이에 인과관계나 설명력이 있다고 단정할 수 없습니다. 다음 단계에서 정량적 방법(예: 하위집단별 "
        f"교차표, 상관분석 등, 이번 단계에서는 미수행)으로 확인이 필요한 가설입니다.\n"
    )

    lines.append("## 5. 앞 단계 병목 관찰과 일치하지 않는 국가\n")
    lines.append("**[패턴으로 관찰되는 국가 특성]**")
    if not_matched:
        lines.append(f"- {', '.join(not_matched)}: 앞 단계 tercile 기반 관찰에서는 Layer1→Layer3 구간 하락이 있었으나, "
                      f"이번 단계의 실제 Gap 값 기준으로는 '상위3분위(Gap 큼)'에 속하지 않았습니다. "
                      f"tercile 구간화와 단순 차감(Gap)은 서로 다른 계산 방식이므로 결과가 항상 일치하지는 않으며, "
                      f"이 불일치 자체가 오류를 의미하지는 않습니다.")
    else:
        lines.append("- 앞 단계에서 direct_within_survey 근거로 관찰된 3개국(러시아·인도·카자흐스탄) 모두 이번 Gap 구간 분류와도 일치했습니다.")
    lines.append("")

    lines.append("## 6. 다음 단계에서 통계적으로 검증할 필요가 있는 가설\n")
    lines.append("**[추가 검증이 필요한 해석/가설]**")
    lines.append("- E1A-1↔B5B-1 Gap이 상위3분위인 국가들의 Gap 크기가 나머지 국가와 통계적으로 유의하게 다른지 (이번 단계는 기술 통계만 수행, 검정 미수행)")
    lines.append("- 조건부 Gap(E4-1↔E4-3)이 큰 국가와 direct Gap(E1A-1↔B5B-1)이 큰 국가가 얼마나 겹치는지, 그 겹침이 우연 수준을 넘는지")
    lines.append("- '한류 관심 부재' 장벽 비율과 direct Gap 크기 사이에 실제 연관 패턴이 있는지 (상관분석은 이번 단계에서 미수행)")
    lines.append("- 소표본(30명 미만) 국가를 제외했을 때도 위 패턴들이 유지되는지")
    lines.append("- E1A-1↔B5B-1 Gap의 국가 간 차이가 각국 표본설계(스크리닝 여부, 표본크기)의 차이로 설명되는 부분은 없는지\n")

    return lines


def write_report_md(lines):
    with open(OUT_REPORT_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"[저장] {OUT_REPORT_MD}")


def main():
    long_rows = load_csv(LONG_CSV)
    profile_rows = load_csv(PROFILE_CSV)
    print(f"[로드] analysis_long: {len(long_rows)}행, country_profile_base: {len(profile_rows)}행")
    assert len(profile_rows) == 23, f"국가 수가 23이 아님: {len(profile_rows)}"

    gap_rows, gap_stats = build_gap_analysis(profile_rows)
    write_gap_csv(gap_rows)

    cond_rows, cond_stats = build_conditional_gap_analysis(profile_rows)
    write_cond_gap_csv(cond_rows)

    barrier_rows = build_barrier_pattern(long_rows, "B13-1A")
    write_barrier_csv(barrier_rows)

    report_lines = build_report_md(gap_rows, gap_stats, cond_rows, cond_stats, barrier_rows)
    write_report_md(report_lines)

    print("\n[요약]")
    print(f" - gap_analysis.csv: {len(gap_rows)}개국, Gap median={gap_stats['median']}%p")
    print(f" - conditional_gap_analysis.csv: {len(cond_rows)}개국, Gap median={cond_stats['median']}%p")
    print(f" - barrier_pattern_analysis.csv: {len(barrier_rows)}개국")


if __name__ == "__main__":
    main()
