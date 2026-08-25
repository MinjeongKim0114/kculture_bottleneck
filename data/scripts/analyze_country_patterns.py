# -*- coding: utf-8 -*-
"""
국가별 패턴 분석 및 병목 프로파일링 (탐색적 서술 분석)

입력(읽기 전용, 수정하지 않음):
  - data/processed/analysis_long.csv
  - data/processed/country_profile_base.csv

원칙(이번 단계에서 절대 하지 않는 것):
  - 종합점수 계산, 국가 순위 산출, 상관/회귀/군집분석
  - 서로 다른 BASE를 가진 값끼리의 직접 차감(Gap) 계산
  - Layer/지표 정의를 임의로 변경하거나 새 국가·지표를 추가하는 것

이번 단계에서 하는 것:
  - 핵심 7개 지표(E1A-1, E4-1, E4-3, B5B-1, B13-1A, B13-2A, 1-35)의 국가별 분포 기술(describe)
  - tercile(3분위) 구간 배정을 통한 "상대적 위치" 비교 (직접 차감이 아닌 순서통계량 기반 기술적 구간화)
  - direct_within_survey(E1A-1/B5B-1, 동일 BASE=전체 응답자) vs conditional(그 외, 서로 다른 BASE) 구분 해석
  - B13-1A/2A 기반 방문 비의향 장벽 패턴 서술
  - "병목 발견"이 아니라 "병목 가능성 관찰"로 표현

산출물:
  - data/processed/country_indicator_distribution.csv
  - data/processed/country_pattern_profile.csv
  - data/processed/country_bottleneck_observations.csv
  - data/processed/country_pattern_analysis_report.md
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

OUT_DIST_CSV = PROCESSED_DIR / "country_indicator_distribution.csv"
OUT_PATTERN_CSV = PROCESSED_DIR / "country_pattern_profile.csv"
OUT_OBS_CSV = PROCESSED_DIR / "country_bottleneck_observations.csv"
OUT_REPORT_MD = PROCESSED_DIR / "country_pattern_analysis_report.md"

AGGREGATE_MARKERS = {"계", "종합", "종합/Top2", "Top2"}

# 핵심 7개 지표 (기존 확정 보고서에서 role='핵심'/'핵심_대표'로 지정된 table_id 그대로 사용, 변경 금지)
CORE_TABLE_IDS = {"E1A-1", "E4-1", "E4-3", "B5B-1", "B13-1A", "B13-2A", "1-35"}

# country_profile_base.csv 의 숫자형 핵심 지표 컬럼과 그 comparability/BASE 정보
# (기존 build_analysis_long.py의 POTENTIAL_META / HALLYU_META 판정을 그대로 인용)
CORE_NUMERIC_INDICATORS = {
    "culture_experience_rate_pct": dict(
        table_id="E1A-1", layer="Layer1_Hallyu_Exposure", label="문화경험률(E1A-1)",
        base_type="전체 응답자", comparability="direct_within_survey",
    ),
    "hallyu_perception_positive_pct": dict(
        table_id="1-35", layer="Layer2_Korea_Perception", label="한류실태 인식긍정률(1-35)",
        base_type="한류경험자(한류실태조사, 별도 패널)", comparability="conditional",
    ),
    "culture_to_korea_positive_pct": dict(
        table_id="E4-1", layer="Layer2_Korea_Perception", label="문화경험→호감도 긍정률(E4-1)",
        base_type="문화경험자(잠재방한객, 전체의 하위집합)", comparability="conditional",
    ),
    "visit_intention_positive_pct": dict(
        table_id="B5B-1", layer="Layer3_Visit_Intention", label="방한의향 있음률(B5B-1)",
        base_type="전체 응답자", comparability="direct_within_survey",
    ),
    "culture_to_visit_positive_pct": dict(
        table_id="E4-3", layer="Layer3_Visit_Intention", label="문화경험→방문의향 긍정률(E4-3)",
        base_type="문화경험자(잠재방한객, 전체의 하위집합)", comparability="conditional",
    ),
}

# E1A-1 / B5B-1 만 동일 survey·동일 BASE(전체 응답자)를 공유 -> direct 비교의 유일한 후보 쌍
DIRECT_COMPARABLE_PAIR = ("culture_experience_rate_pct", "visit_intention_positive_pct")


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


# ---------------------------------------------------------------------------
# 1. 핵심 7개 지표의 국가별 값 정리 + 지표별 국가 분포 확인
# ---------------------------------------------------------------------------


def compute_distribution(values):
    values = sorted(values)
    n = len(values)
    q1, med, q3 = statistics.quantiles(values, n=4)[0], statistics.median(values), statistics.quantiles(values, n=4)[2]
    return dict(
        n=n, min=min(values), q1=q1, median=med, q3=q3, max=max(values),
        mean=statistics.mean(values), stdev=statistics.pstdev(values),
    )


def tercile_labels(values_by_country):
    """23개국 값을 정렬 후 3분위(하위/중위/상위)로 구간화한다.
    이는 직접 차감(Gap)이 아니라 순서통계량(quantile) 기반의 기술적 구간화이다."""
    items = sorted(values_by_country.items(), key=lambda kv: kv[1])
    n = len(items)
    cut1 = n // 3
    cut2 = n - n // 3
    labels = {}
    for i, (country, val) in enumerate(items):
        if i < cut1:
            labels[country] = "하위3분위"
        elif i < cut2:
            labels[country] = "중위3분위"
        else:
            labels[country] = "상위3분위"
    return labels


def build_distribution_and_pattern(profile_rows):
    dist_rows = []
    tier_by_indicator = {}
    values_by_indicator = {}

    for col, meta in CORE_NUMERIC_INDICATORS.items():
        values_by_country = {r["country"]: to_float(r[col]) for r in profile_rows}
        values_by_country = {c: v for c, v in values_by_country.items() if v is not None}
        values_by_indicator[col] = values_by_country
        stats = compute_distribution(list(values_by_country.values()))
        dist_rows.append(dict(
            indicator=col, table_id=meta["table_id"], layer=meta["layer"],
            comparability=meta["comparability"], base_type=meta["base_type"],
            n_countries=stats["n"], min=round(stats["min"], 2), q1=round(stats["q1"], 2),
            median=round(stats["median"], 2), q3=round(stats["q3"], 2), max=round(stats["max"], 2),
            mean=round(stats["mean"], 2), stdev=round(stats["stdev"], 2),
        ))
        tier_by_indicator[col] = tercile_labels(values_by_country)

    # 국가별 패턴 프로파일 (값 + tier)
    pattern_rows = []
    for r in profile_rows:
        country = r["country"]
        row = {"country": country}
        for col in CORE_NUMERIC_INDICATORS:
            val = to_float(r[col])
            row[col] = val
            row[f"{col}_tier"] = tier_by_indicator[col].get(country) if val is not None else None
        row["top_visit_barrier"] = r["top_visit_barrier"]
        row["top_visit_barrier_rate_pct"] = to_float(r["top_visit_barrier_rate_pct"])
        pattern_rows.append(row)

    return dist_rows, pattern_rows, tier_by_indicator, values_by_indicator


def write_dist_csv(dist_rows):
    fieldnames = ["indicator", "table_id", "layer", "comparability", "base_type",
                  "n_countries", "min", "q1", "median", "q3", "max", "mean", "stdev"]
    with open(OUT_DIST_CSV, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in dist_rows:
            w.writerow(r)
    print(f"[저장] {OUT_DIST_CSV} ({len(dist_rows)}행)")


def write_pattern_csv(pattern_rows):
    fieldnames = ["country"]
    for col in CORE_NUMERIC_INDICATORS:
        fieldnames += [col, f"{col}_tier"]
    fieldnames += ["top_visit_barrier", "top_visit_barrier_rate_pct"]
    with open(OUT_PATTERN_CSV, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in pattern_rows:
            w.writerow(r)
    print(f"[저장] {OUT_PATTERN_CSV} ({len(pattern_rows)}행)")


# ---------------------------------------------------------------------------
# 2. B13-1A 기반 국가별 상위 장벽(top-3) 추출
# ---------------------------------------------------------------------------


def top_barriers_by_country(long_rows, table_id="B13-1A", top_n=3):
    by_country = defaultdict(list)
    for r in long_rows:
        if r["table_id"] != table_id:
            continue
        if r["response_option"] in AGGREGATE_MARKERS:
            continue
        val = to_float(r["value"])
        if val is None:
            continue
        by_country[r["country"]].append((r["response_option"], val, to_float(r["sample_n"])))
    result = {}
    for country, items in by_country.items():
        items.sort(key=lambda x: -x[1])
        result[country] = items[:top_n]
    return result


# ---------------------------------------------------------------------------
# 3. 병목 "가능성 관찰" 로직 (직접 비교쌍 vs conditional 지표 구분)
# ---------------------------------------------------------------------------


def build_observations(pattern_rows, top_barriers_1a, top_barriers_2a):
    observations = []

    for row in pattern_rows:
        country = row["country"]

        # (A) direct_within_survey 쌍: culture_experience_rate_pct vs visit_intention_positive_pct
        #     동일 survey·동일 BASE(전체 응답자)이므로 "상대적 구간 하락"을 병목 '가능성'으로 관찰할 근거가
        #     conditional 지표보다 상대적으로 강함. 단, 여전히 실제 수치 차감(Gap)은 하지 않음.
        exp_tier = row["culture_experience_rate_pct_tier"]
        vis_tier = row["visit_intention_positive_pct_tier"]
        tier_rank = {"하위3분위": 0, "중위3분위": 1, "상위3분위": 2}
        if exp_tier and vis_tier and tier_rank[exp_tier] - tier_rank[vis_tier] >= 1:
            observations.append(dict(
                country=country, comparability_class="direct_within_survey",
                observation_type="Layer1->Layer3 상대적 구간 하락",
                detail=(
                    f"문화경험률(E1A-1)은 {exp_tier}, 방한의향 있음률(B5B-1)은 {vis_tier}로 "
                    f"동일 모집단(전체 응답자) 내에서 구간이 하락함"
                ),
                confidence="병목 가능성이 관찰됨 (direct_within_survey 쌍이므로 conditional 지표보다 해석 근거가 상대적으로 강함, "
                           "그러나 실제 수치 차감(Gap)이나 통계적 유의성 검정은 수행하지 않았으므로 '발견'으로 단정하지 않음)",
            ))

        # (B) conditional 지표: E4-1/E4-3/1-35 는 서로 다른 BASE(하위집합 또는 별도 패널)이므로
        #     tier 하락을 관찰하더라도 훨씬 약한 신뢰도로만 서술한다.
        e4_1_tier = row["culture_to_korea_positive_pct_tier"]
        e4_3_tier = row["culture_to_visit_positive_pct_tier"]
        if e4_1_tier and e4_3_tier and tier_rank[e4_1_tier] - tier_rank[e4_3_tier] >= 1:
            observations.append(dict(
                country=country, comparability_class="conditional",
                observation_type="Layer2->Layer3 상대적 구간 하락 (잠재방한객 문화경험자 하위집합 내부)",
                detail=(
                    f"문화경험자 중 호감도 긍정률(E4-1)은 {e4_1_tier}, 같은 문화경험자 중 방문의향 긍정률(E4-3)은 "
                    f"{e4_3_tier}로 구간이 하락함 (두 지표 모두 '문화경험자'라는 같은 하위집합을 BASE로 공유하므로 "
                    f"E1A-1/B5B-1 쌍만큼은 아니지만 어느 정도 비교 근거가 있음)"
                ),
                confidence="병목 가능성이 관찰됨 (conditional, 같은 하위집단 내부 비교이나 표본 구성 차이 가능성 있어 발견으로 단정 불가)",
            ))

        h_tier = row["hallyu_perception_positive_pct_tier"]
        if h_tier and e4_1_tier and h_tier != e4_1_tier:
            observations.append(dict(
                country=country, comparability_class="conditional",
                observation_type="한류실태(1-35) vs 잠재방한객(E4-1) 인식긍정률 구간 불일치",
                detail=(
                    f"한류실태조사 인식긍정률(1-35, 한류경험자 패널)은 {h_tier}, "
                    f"잠재방한객조사 호감도긍정률(E4-1, 문화경험자 하위집합)은 {e4_1_tier}로 구간이 다름"
                ),
                confidence="참고 관찰 (서로 다른 조사·별도 스크리닝된 패널이므로 병목 판단 근거로 사용하지 않고 "
                           "두 조사의 응답 경향 차이를 보여주는 참고 정보로만 기록)",
            ))

        # (C) 방한 비의향 장벽 중 '한류' 관련 요인이 상위(top-3)에 포함되는지
        top3 = top_barriers_1a.get(country, [])
        top3_labels = [t[0] for t in top3]
        hallyu_barrier = [t for t in top3 if "한류" in t[0]]
        if hallyu_barrier:
            observations.append(dict(
                country=country, comparability_class="conditional",
                observation_type="방한 비의향 장벽 중 한류 콘텐츠 관심 부재가 상위 요인",
                detail=(
                    f"방문 비의향자(B13-1A) 상위 사유 Top3: {top3_labels}, "
                    f"이 중 '한류(한국 문화 콘텐츠) 문화 관련 관심 부재'가 {hallyu_barrier[0][1]:.1f}%로 포함됨"
                ),
                confidence="병목 가능성이 관찰됨 (단, B13-1A의 BASE는 '방문 비의향자'라는 별도 하위집단이므로 "
                           "이 국가의 전체 모집단 특성과 직접 연결해 해석하지 않도록 주의)",
            ))

    return observations


def write_obs_csv(observations):
    fieldnames = ["country", "comparability_class", "observation_type", "detail", "confidence"]
    with open(OUT_OBS_CSV, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in observations:
            w.writerow(r)
    print(f"[저장] {OUT_OBS_CSV} ({len(observations)}행)")


# ---------------------------------------------------------------------------
# 4. 보고서(md) 작성
# ---------------------------------------------------------------------------


def build_report_md(dist_rows, pattern_rows, tier_by_indicator, top_barriers_1a, observations):
    lines = []
    lines.append("# 국가별 패턴 분석 및 병목 프로파일링 보고서\n")
    lines.append("이 보고서는 `analysis_long.csv`, `country_profile_base.csv`를 입력으로 하는 탐색적 서술 분석입니다. "
                  "종합점수·순위·상관/회귀/군집분석은 수행하지 않았으며, 서로 다른 BASE의 값을 직접 차감(Gap)하지 않았습니다. "
                  "구간 배정(3분위)은 값을 정렬한 순서통계량 기반의 기술적 구간화이며, "
                  "그 자체가 '병목의 발견'을 의미하지 않고 다음 단계 검증이 필요한 '관찰'로만 취급합니다.\n")

    lines.append("## 1. 핵심 7개 지표의 전체 23개국 분포\n")
    lines.append("| indicator | table_id | layer | comparability | BASE | n | min | q1 | median | q3 | max | mean | stdev |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for r in dist_rows:
        lines.append(
            f"| {r['indicator']} | {r['table_id']} | {r['layer']} | {r['comparability']} | {r['base_type']} | "
            f"{r['n_countries']} | {r['min']} | {r['q1']} | {r['median']} | {r['q3']} | {r['max']} | {r['mean']} | {r['stdev']} |"
        )
    lines.append("\n(B13-1A/B13-2A는 다중응답·항목별 표라 위 표에는 포함하지 않았으며, 3절의 장벽 패턴에서 별도로 다룹니다.)\n")

    lines.append("## 2. Direct vs Conditional 지표 구분 해석\n")
    lines.append("- **direct_within_survey** (문화경험률 E1A-1 ↔ 방한의향률 B5B-1): 두 지표 모두 '잠재방한객조사(일반외국인) "
                  "전체 응답자(n=16,360)'라는 동일 BASE를 공유합니다. 같은 모집단을 서로 다른 두 시점(경험 여부 / 방문 의향)에서 "
                  "관찰한 값이므로, 이 두 지표 사이의 상대적 구간 변화는 다른 조합보다 해석 근거가 상대적으로 강합니다.")
    lines.append("- **conditional** (E4-1, E4-3, 1-35, B13 계열): 각각 BASE가 다릅니다 — E4-1/E4-3은 '문화경험자'라는 "
                  "전체의 하위집합, B13 계열은 '방문 비의향자'라는 또 다른 하위집합, 1-35는 한류실태조사라는 완전히 별도로 "
                  "모집된 독립 패널입니다. 이들 사이의 구간 비교는 참고 수준으로만 다루었습니다.\n")

    lines.append("## 3. 국가별 핵심 패턴 (3분위 구간 프로파일)\n")
    lines.append("| country | 문화경험률(E1A-1) | 한류인식긍정(1-35) | 문화→호감(E4-1) | 방한의향(B5B-1) | 문화→방문의향(E4-3) |")
    lines.append("|---|---|---|---|---|---|")
    for row in sorted(pattern_rows, key=lambda r: r["country"]):
        if row["hallyu_perception_positive_pct_tier"]:
            hallyu_cell = f"{row['hallyu_perception_positive_pct']:.1f}% ({row['hallyu_perception_positive_pct_tier']})"
        else:
            hallyu_cell = "-"
        lines.append(
            f"| {row['country']} | "
            f"{row['culture_experience_rate_pct']:.1f}% ({row['culture_experience_rate_pct_tier']}) | "
            f"{hallyu_cell} | "
            f"{row['culture_to_korea_positive_pct']:.1f}% ({row['culture_to_korea_positive_pct_tier']}) | "
            f"{row['visit_intention_positive_pct']:.1f}% ({row['visit_intention_positive_pct_tier']}) | "
            f"{row['culture_to_visit_positive_pct']:.1f}% ({row['culture_to_visit_positive_pct_tier']}) |"
        )
    lines.append("")

    lines.append("## 4. 방문 비의향 장벽 패턴 (B13-1A, 1+2+3순위 기준, 상위 3개)\n")
    lines.append("| country | 1순위 사유 | 2순위 사유 | 3순위 사유 |")
    lines.append("|---|---|---|---|")
    for country in sorted(top_barriers_1a):
        items = top_barriers_1a[country]
        cells = [f"{lbl}({val:.1f}%)" for lbl, val, n in items]
        while len(cells) < 3:
            cells.append("-")
        lines.append(f"| {country} | {cells[0]} | {cells[1]} | {cells[2]} |")
    lines.append("")

    lines.append("## 5. 국가별 잠재 병목 관찰 (병목 '발견'이 아닌 '가능성 관찰')\n")
    by_country_obs = defaultdict(list)
    for o in observations:
        by_country_obs[o["country"]].append(o)
    for country in sorted(by_country_obs):
        lines.append(f"### {country}")
        for o in by_country_obs[country]:
            lines.append(f"- **[{o['comparability_class']}] {o['observation_type']}**: {o['detail']}")
            lines.append(f"  - 신뢰도 표현: {o['confidence']}")
        lines.append("")

    lines.append("## 6. 데이터 해석 시 BASE/comparability 주의사항\n")
    lines.append("- E1A-1과 B5B-1만 동일 BASE(전체 응답자)를 공유합니다. 이 둘의 관계는 다음 단계에서 실제 수치 Gap을 "
                  "계산할 정당성이 있는 유일한 핵심-지표 쌍입니다.")
    lines.append("- E4-1/E4-3은 서로 같은 '문화경험자' 하위집합을 공유하므로 둘 사이의 비교는 어느 정도 근거가 있으나, "
                  "E1A-1/B5B-1과 섞어서 하나의 Funnel 수치로 압축하면 안 됩니다.")
    lines.append("- 1-35(한류실태조사)는 잠재방한객조사와 완전히 별도로 모집된 '한류 경험자 전용 패널'입니다. "
                  "E4-1/1-35의 구간 불일치는 두 조사의 응답 경향 차이일 뿐, 동일 인구집단의 변화로 해석해서는 안 됩니다.")
    lines.append("- B13-1A/2A(장벽)는 '방문 비의향자'만 대상이므로, 이 지표의 패턴을 해당 국가의 '전체 국민 성향'으로 "
                  "일반화하면 안 됩니다. 또한 일부 국가는 비의향자 표본이 작아(예: 일본 165명) 해석 시 유의해야 합니다.")
    lines.append("- 3분위(tercile) 구간은 정렬 순서에 따른 상대적 위치일 뿐이며, 구간 간 실제 값 차이의 크기(=통계적으로 "
                  "의미 있는 차이인지)는 검증하지 않았습니다.\n")

    lines.append("## 7. 아직 계산할 수 없는 것 / 다음 분석 단계에서 검증해야 할 것\n")
    lines.append("- **E1A-1 ↔ B5B-1 실제 수치 Gap**: 동일 BASE를 공유하므로 다음 단계에서 정당하게 계산 가능한 유일한 "
                  "핵심 지표 쌍입니다. 이번 단계에서는 계산하지 않았습니다.")
    lines.append("- **tier(3분위) 하락이 통계적으로 유의미한지**: 현재는 순서 기반 구간화만 했을 뿐, 구간 간 실제 값 차이의 "
                  "크기나 신뢰구간을 검증하지 않았습니다.")
    lines.append("- **conditional 지표(E4-1/E4-3/1-35/B13) 간 비교의 타당성**: 서로 다른 BASE를 가진 지표를 나란히 놓고 "
                  "패턴을 관찰했지만, 이것이 실제로 같은 현상의 다른 단면인지, 표본 구성 차이로 인한 착시인지는 "
                  "검증되지 않았습니다.")
    lines.append("- **소표본 국가의 신뢰도**: B13 계열에서 비의향자 표본이 30명 미만인 국가는 개별적으로 확인이 필요합니다 "
                  "(원본 PDF도 '30표본 미만은 통계적 유의성 평가를 위한 유효 표본 부족'이라고 명시).")
    lines.append("- **개인 단위 인과관계**: 이번 분석의 모든 지표는 국가 단위 집계값이며, 응답자 개인이 문화 경험에서 "
                  "방문 의향으로 실제로 '전환'되었는지는 어떤 단계에서도 확인할 수 없습니다.")
    lines.append("- **상관/회귀/군집 등 정량적 검증**: 이번 단계에서 관찰된 패턴이 실제로 유의미한 그룹을 이루는지는 "
                  "다음 단계의 정량 분석(상관/군집 등, 이번에는 미수행)에서 검증해야 합니다.\n")

    return lines


def write_report_md(lines):
    with open(OUT_REPORT_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"[저장] {OUT_REPORT_MD}")


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def main():
    long_rows = load_csv(LONG_CSV)
    profile_rows = load_csv(PROFILE_CSV)
    print(f"[로드] analysis_long: {len(long_rows)}행, country_profile_base: {len(profile_rows)}행")
    assert len(profile_rows) == 23, f"국가 수가 23이 아님: {len(profile_rows)}"

    dist_rows, pattern_rows, tier_by_indicator, values_by_indicator = build_distribution_and_pattern(profile_rows)
    write_dist_csv(dist_rows)
    write_pattern_csv(pattern_rows)

    top_barriers_1a = top_barriers_by_country(long_rows, "B13-1A", top_n=3)
    top_barriers_2a = top_barriers_by_country(long_rows, "B13-2A", top_n=1)

    observations = build_observations(pattern_rows, top_barriers_1a, top_barriers_2a)
    write_obs_csv(observations)

    report_lines = build_report_md(dist_rows, pattern_rows, tier_by_indicator, top_barriers_1a, observations)
    write_report_md(report_lines)

    print("\n[요약]")
    print(f" - country_indicator_distribution.csv: {len(dist_rows)}개 지표")
    print(f" - country_pattern_profile.csv: {len(pattern_rows)}개국")
    print(f" - country_bottleneck_observations.csv: {len(observations)}건 관찰")


if __name__ == "__main__":
    main()
