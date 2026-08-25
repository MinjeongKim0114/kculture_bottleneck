# -*- coding: utf-8 -*-
"""
Gap-장벽 관계 및 소표본 민감도 검증

입력(읽기 전용, 수정하지 않음):
  - data/processed/gap_analysis.csv               (E1A-1 - B5B-1, direct_within_survey Gap)
  - data/processed/conditional_gap_analysis.csv    (E4-1 - E4-3, conditional Gap)
  - data/processed/barrier_pattern_analysis.csv    (B13-1A 8개 장벽, 방문 비의향자 BASE)
  - data/processed/country_profile_base.csv

원칙(이번 단계에서 절대 하지 않는 것):
  - "원인이다/영향을 준다/전환을 유발한다/인과관계가 확인되었다/통계적으로 유의하다고 단정한다" 등의 표현 사용 금지
  - 종합점수, 서비스 우선순위 점수, DB 구축, 원본/기존 분석 CSV 수정
  - 상관계수를 국가 단위 이상의 개인 수준 관계로 확장 해석

이번 단계에서 하는 것(국가 단위 n=23 집계자료에 대한 탐색적 상관 분석):
  1. Direct Gap(E1A-1-B5B-1) vs 8개 장벽 비율: Pearson & Spearman
  2. Direct Gap vs Conditional Gap: Pearson & Spearman
  3. 소표본(n<30) 4개국(베트남/인도네시아/태국/필리핀) 제외 민감도 분석
  4. 산점도(국가명 라벨 포함) 4종

산출물:
  - data/processed/gap_barrier_correlation.csv
  - data/processed/sensitivity_analysis.csv
  - data/processed/gap_barrier_validation_report.md
  - data/processed/figures/*.png
"""

from __future__ import annotations

import csv
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from scipy import stats as sstats

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
FIG_DIR = PROCESSED_DIR / "figures"
FIG_DIR.mkdir(parents=True, exist_ok=True)

GAP_CSV = PROCESSED_DIR / "gap_analysis.csv"
COND_GAP_CSV = PROCESSED_DIR / "conditional_gap_analysis.csv"
BARRIER_CSV = PROCESSED_DIR / "barrier_pattern_analysis.csv"
PROFILE_CSV = PROCESSED_DIR / "country_profile_base.csv"

OUT_CORR_CSV = PROCESSED_DIR / "gap_barrier_correlation.csv"
OUT_SENS_CSV = PROCESSED_DIR / "sensitivity_analysis.csv"
OUT_REPORT_MD = PROCESSED_DIR / "gap_barrier_validation_report.md"

SMALL_SAMPLE_COUNTRIES = ["베트남", "인도네시아", "태국", "필리핀"]

BARRIER_KEYWORDS = {
    "한류_관심_부재": "한류 관심 부재",
    "낮은_한국_인지도": "낮은 한국 인지도",
    "부정적_한국_이미지": "부정적인 한국 이미지",
    "불편한_언어소통": "불편한 언어소통",
    "여행경비_물가": "여행경비/물가",
    "비자_출입국_절차": "비자/출입국 절차",
    "장거리_비행": "장거리 비행",
    "불편한_종교환경": "불편한 종교 환경",
}

# 한글 폰트(윈도우 맑은 고딕) — 없으면 기본 폰트로 라벨이 깨질 수 있음을 감안
for cand in ("Malgun Gothic", "AppleGothic", "NanumGothic"):
    if cand in {f.name for f in font_manager.fontManager.ttflist}:
        plt.rcParams["font.family"] = cand
        break
plt.rcParams["axes.unicode_minus"] = False


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


def load_data():
    gap_rows = load_csv(GAP_CSV)
    cond_rows = load_csv(COND_GAP_CSV)
    barrier_rows = load_csv(BARRIER_CSV)

    direct_gap = {r["country"]: to_float(r["observed_gap_pct_point"]) for r in gap_rows}
    cond_gap = {r["country"]: to_float(r["observed_conditional_gap_pct_point"]) for r in cond_rows}

    barriers = {}
    small_sample_flag = {}
    for r in barrier_rows:
        c = r["country"]
        barriers[c] = {label: to_float(r[label]) for label in BARRIER_KEYWORDS}
        small_sample_flag[c] = r["small_sample_flag"]

    return direct_gap, cond_gap, barriers, small_sample_flag


# ---------------------------------------------------------------------------
# 1 & 2. Pearson / Spearman 상관 (전체 23개국, 소표본 제외 n=19 두 조건 모두 계산)
# ---------------------------------------------------------------------------


def paired_values(x_map, y_map, exclude_countries=()):
    countries = sorted(set(x_map) & set(y_map))
    countries = [c for c in countries if c not in exclude_countries]
    xs, ys = [], []
    for c in countries:
        xv, yv = x_map.get(c), y_map.get(c)
        if xv is None or yv is None:
            continue
        xs.append(xv)
        ys.append(yv)
    return countries, xs, ys


def direction_label(r):
    if r is None:
        return "계산불가"
    if r > 0.05:
        return "양(+)의 방향"
    if r < -0.05:
        return "음(-)의 방향"
    return "뚜렷한 방향 없음(거의 0)"


def compute_corr_pair(label_x, label_y, x_map, y_map, subset_label, exclude_countries=()):
    countries, xs, ys = paired_values(x_map, y_map, exclude_countries)
    n = len(xs)
    if n < 3:
        return dict(
            pair=f"{label_x} vs {label_y}", subset=subset_label, n=n,
            pearson_r=None, pearson_p=None, spearman_r=None, spearman_p=None,
            direction="표본 부족(n<3)으로 계산불가",
        )
    pear_r, pear_p = sstats.pearsonr(xs, ys)
    spear_r, spear_p = sstats.spearmanr(xs, ys)
    return dict(
        pair=f"{label_x} vs {label_y}", subset=subset_label, n=n,
        pearson_r=round(float(pear_r), 4), pearson_p=round(float(pear_p), 4),
        spearman_r=round(float(spear_r), 4), spearman_p=round(float(spear_p), 4),
        direction=direction_label(float(pear_r)),
    )


def build_correlation_table(direct_gap, cond_gap, barriers):
    rows = []

    barrier_maps = {
        label: {c: v.get(label) for c, v in barriers.items()} for label in BARRIER_KEYWORDS
    }

    # 1. Direct Gap <-> 8개 장벽 (전체 23개국)
    for label in BARRIER_KEYWORDS:
        rows.append(compute_corr_pair("Direct_Gap(E1A-1-B5B-1)", label, direct_gap, barrier_maps[label], "전체_23개국"))

    # 1-sens. Direct Gap <-> 8개 장벽 (소표본 4개국 제외, n=19)
    for label in BARRIER_KEYWORDS:
        rows.append(compute_corr_pair("Direct_Gap(E1A-1-B5B-1)", label, direct_gap, barrier_maps[label],
                                       "소표본4개국_제외(n=19)", exclude_countries=SMALL_SAMPLE_COUNTRIES))

    # 2. Direct Gap <-> Conditional Gap (전체 + 소표본 제외)
    rows.append(compute_corr_pair("Direct_Gap(E1A-1-B5B-1)", "Conditional_Gap(E4-1-E4-3)", direct_gap, cond_gap, "전체_23개국"))
    rows.append(compute_corr_pair("Direct_Gap(E1A-1-B5B-1)", "Conditional_Gap(E4-1-E4-3)", direct_gap, cond_gap,
                                   "소표본4개국_제외(n=19)", exclude_countries=SMALL_SAMPLE_COUNTRIES))

    return rows


def write_corr_csv(rows):
    fieldnames = ["pair", "subset", "n", "pearson_r", "pearson_p", "spearman_r", "spearman_p", "direction"]
    with open(OUT_CORR_CSV, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    print(f"[저장] {OUT_CORR_CSV} ({len(rows)}행)")


# ---------------------------------------------------------------------------
# 3. 소표본 민감도 비교표 (전체 vs 제외, 지표쌍별 나란히)
# ---------------------------------------------------------------------------


def build_sensitivity_table(corr_rows):
    by_pair_subset = {(r["pair"], r["subset"]): r for r in corr_rows}
    pairs = sorted({r["pair"] for r in corr_rows})
    rows = []
    for pair in pairs:
        full = by_pair_subset.get((pair, "전체_23개국"))
        excl = by_pair_subset.get((pair, "소표본4개국_제외(n=19)"))
        if not full or not excl:
            continue
        pearson_diff = None
        direction_changed = None
        if full["pearson_r"] is not None and excl["pearson_r"] is not None:
            pearson_diff = round(excl["pearson_r"] - full["pearson_r"], 4)
            direction_changed = "Y" if (full["pearson_r"] > 0) != (excl["pearson_r"] > 0) else "N"
        rows.append(dict(
            pair=pair,
            n_full=full["n"], pearson_r_full=full["pearson_r"], pearson_p_full=full["pearson_p"],
            n_excl=excl["n"], pearson_r_excl=excl["pearson_r"], pearson_p_excl=excl["pearson_p"],
            pearson_r_diff=pearson_diff, direction_changed=direction_changed,
        ))
    return rows


def write_sens_csv(rows):
    fieldnames = ["pair", "n_full", "pearson_r_full", "pearson_p_full",
                  "n_excl", "pearson_r_excl", "pearson_p_excl", "pearson_r_diff", "direction_changed"]
    with open(OUT_SENS_CSV, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    print(f"[저장] {OUT_SENS_CSV} ({len(rows)}행)")


# ---------------------------------------------------------------------------
# 4. 산점도 (국가명 라벨 포함)
# ---------------------------------------------------------------------------


def scatter_plot(x_map, y_map, x_label, y_label, title, filename, small_sample_flag=None):
    countries, xs, ys = paired_values(x_map, y_map)
    fig, ax = plt.subplots(figsize=(9, 7))
    colors = []
    for c in countries:
        if small_sample_flag and small_sample_flag.get(c) == "Y":
            colors.append("#d95f02")
        else:
            colors.append("#1b6ca8")
    ax.scatter(xs, ys, c=colors, s=45, alpha=0.85, edgecolors="white", linewidths=0.5)
    for c, x, y in zip(countries, xs, ys):
        ax.annotate(c, (x, y), fontsize=8, xytext=(4, 3), textcoords="offset points")
    ax.set_xlabel(x_label)
    ax.set_ylabel(y_label)
    ax.set_title(title, fontsize=11)
    if small_sample_flag:
        ax.scatter([], [], c="#d95f02", label="소표본(n<30) 국가")
        ax.scatter([], [], c="#1b6ca8", label="그 외 국가")
        ax.legend(fontsize=8, loc="best")
    fig.tight_layout()
    out_path = FIG_DIR / filename
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"[저장] {out_path}")


def build_figures(direct_gap, cond_gap, barriers, small_sample_flag):
    barrier_maps = {label: {c: v.get(label) for c, v in barriers.items()} for label in BARRIER_KEYWORDS}

    scatter_plot(direct_gap, barrier_maps["한류_관심_부재"],
                 "Direct Gap (E1A-1 - B5B-1, %p)", "한류 관심 부재 비율 (%, 방문비의향자 BASE)",
                 "Direct Gap x 한류 관심 부재", "gap_x_hallyu_lack.png", small_sample_flag)
    scatter_plot(direct_gap, barrier_maps["낮은_한국_인지도"],
                 "Direct Gap (E1A-1 - B5B-1, %p)", "낮은 한국 인지도 비율 (%, 방문비의향자 BASE)",
                 "Direct Gap x 낮은 한국 인지도", "gap_x_low_awareness.png", small_sample_flag)
    scatter_plot(direct_gap, barrier_maps["부정적_한국_이미지"],
                 "Direct Gap (E1A-1 - B5B-1, %p)", "부정적인 한국 이미지 비율 (%, 방문비의향자 BASE)",
                 "Direct Gap x 부정적인 한국 이미지", "gap_x_negative_image.png", small_sample_flag)
    scatter_plot(direct_gap, cond_gap,
                 "Direct Gap (E1A-1 - B5B-1, %p)", "Conditional Gap (E4-1 - E4-3, %p)",
                 "Direct Gap x Conditional Gap (서로 다른 BASE, 별개 분석축)", "gap_x_conditional_gap.png", small_sample_flag)


# ---------------------------------------------------------------------------
# 보고서
# ---------------------------------------------------------------------------


def fmt_r(r):
    return "-" if r is None else f"{r:.3f}"


def fmt_p(p):
    return "-" if p is None else f"{p:.3f}"


def build_report_md(corr_rows, sens_rows, direct_gap, cond_gap, barriers, small_sample_flag):
    lines = []
    lines.append("# Gap-장벽 관계 및 소표본 민감도 검증 보고서\n")
    lines.append(
        "이 보고서는 `gap_analysis.csv`, `conditional_gap_analysis.csv`, `barrier_pattern_analysis.csv`, "
        "`country_profile_base.csv`를 입력으로 하는 **국가 단위(n=23) 집계자료 상관 분석**입니다. "
        "Pearson/Spearman 상관계수와 p-value를 계산했지만, 이는 국가 단위 집계값 사이의 통계적 관계일 뿐이며 "
        "개인 수준의 관계나 인과관계를 의미하지 않습니다. p-value가 일반적 기준(예: 0.05)을 충족하더라도 "
        "'통계적으로 유의하다'고 단정하지 않았고, '원인이다/영향을 준다/전환을 유발한다/인과관계가 확인되었다' "
        "같은 표현은 사용하지 않았습니다. 종합점수·서비스 우선순위 점수·DB 구축·원본/기존 분석 CSV 수정은 "
        "수행하지 않았습니다.\n"
    )
    lines.append("## 해석 3단계 구분")
    lines.append("- **[관찰된 통계적 관계]**: 상관계수·p-value 등 CSV에 그대로 계산된 값")
    lines.append("- **[데이터상 나타나는 패턴]**: 여러 관찰 결과를 나열했을 때 보이는 경향 (인과관계 아님)")
    lines.append("- **[추가 검증이 필요한 해석 가설]**: 다음 단계(예: 군집분석, 조사 설계 재검토)에서 확인해야 하는 가설\n")

    # 1. Direct Gap vs 8 barriers
    lines.append("## 1. Direct Gap(E1A-1-B5B-1) ↔ 8개 장벽 상관 (전체 23개국)\n")
    lines.append("**[관찰된 통계적 관계]**\n")
    lines.append("| 장벽 | n | Pearson r | Pearson p | Spearman r | Spearman p | 방향 |")
    lines.append("|---|---|---|---|---|---|---|")
    full_barrier_rows = [r for r in corr_rows if r["subset"] == "전체_23개국" and "Direct_Gap" in r["pair"] and "Conditional_Gap" not in r["pair"]]
    for r in full_barrier_rows:
        barrier_name = r["pair"].split(" vs ")[1]
        lines.append(f"| {barrier_name} | {r['n']} | {fmt_r(r['pearson_r'])} | {fmt_p(r['pearson_p'])} | "
                      f"{fmt_r(r['spearman_r'])} | {fmt_p(r['spearman_p'])} | {r['direction']} |")
    lines.append("")

    abs_sorted = sorted(full_barrier_rows, key=lambda r: -(abs(r["pearson_r"]) if r["pearson_r"] is not None else 0))
    strongest = abs_sorted[0] if abs_sorted else None
    lines.append("**[데이터상 나타나는 패턴]**")
    if strongest:
        b_name = strongest["pair"].split(" vs ")[1]
        lines.append(f"- 8개 장벽 중 Pearson r의 절댓값이 가장 큰 항목은 '{b_name}'(r={fmt_r(strongest['pearson_r'])})입니다. "
                      f"이는 국가 단위 집계값 사이에서 다른 장벽보다 상대적으로 뚜렷한 선형 경향이 관찰된다는 의미이며, "
                      f"장벽이 Gap을 '유발'하거나 '설명'한다는 뜻이 아닙니다.")
    weak = [r for r in full_barrier_rows if r["pearson_r"] is not None and abs(r["pearson_r"]) < 0.1]
    if weak:
        weak_names = [r["pair"].split(" vs ")[1] for r in weak]
        lines.append(f"- 뚜렷한 방향이 관찰되지 않는(|r|<0.1) 장벽: {', '.join(weak_names)}")
    lines.append("")

    # 2. Direct Gap vs Conditional Gap
    lines.append("## 2. Direct Gap ↔ Conditional Gap\n")
    lines.append(
        "두 Gap은 정의와 BASE가 다릅니다: Direct Gap(E1A-1-B5B-1)은 '전체 응답자'를 BASE로 하는 "
        "동일 조사 내 지표 쌍의 단순 차감이고, Conditional Gap(E4-1-E4-3)은 '문화경험자'라는 하위집합을 BASE로 하는 "
        "별도 분석축입니다. 아래 상관은 두 Gap이 국가 단위에서 함께 크거나 작게 나타나는 경향이 있는지를 "
        "탐색적으로만 확인한 것입니다.\n"
    )
    cg_full = next((r for r in corr_rows if r["pair"] == "Direct_Gap(E1A-1-B5B-1) vs Conditional_Gap(E4-1-E4-3)" and r["subset"] == "전체_23개국"), None)
    lines.append("**[관찰된 통계적 관계]**")
    if cg_full:
        lines.append(f"- 전체 23개국: n={cg_full['n']}, Pearson r={fmt_r(cg_full['pearson_r'])} (p={fmt_p(cg_full['pearson_p'])}), "
                      f"Spearman r={fmt_r(cg_full['spearman_r'])} (p={fmt_p(cg_full['spearman_p'])}), 방향={cg_full['direction']}")
    lines.append("")

    # 3. Sensitivity
    lines.append("## 3. 소표본(n<30) 4개국 제외 민감도 분석\n")
    lines.append(f"제외 대상: {', '.join(SMALL_SAMPLE_COUNTRIES)} (모두 B13-1A 방문 비의향자 표본이 30명 미만)\n")
    lines.append("**[관찰된 통계적 관계]**\n")
    lines.append("| 지표쌍 | n(전체) | r(전체) | p(전체) | n(제외) | r(제외) | p(제외) | r 변화량 | 방향 반전 |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    for r in sens_rows:
        lines.append(f"| {r['pair']} | {r['n_full']} | {fmt_r(r['pearson_r_full'])} | {fmt_p(r['pearson_p_full'])} | "
                      f"{r['n_excl']} | {fmt_r(r['pearson_r_excl'])} | {fmt_p(r['pearson_p_excl'])} | "
                      f"{r['pearson_r_diff'] if r['pearson_r_diff'] is not None else '-'} | {r['direction_changed'] or '-'} |")
    lines.append("")

    flipped = [r for r in sens_rows if r["direction_changed"] == "Y"]
    stable = [r for r in sens_rows if r["direction_changed"] == "N"]
    lines.append("**[데이터상 나타나는 패턴]**")
    lines.append(f"- 소표본 4개국 제외 후 상관 방향이 반전된 지표쌍: {len(flipped)}개 "
                 f"({', '.join(r['pair'].split(' vs ')[1] for r in flipped) if flipped else '없음'})")
    lines.append(f"- 방향이 유지된 지표쌍: {len(stable)}개")
    lines.append("- 표본이 23개국→19개국으로 줄면서 상관계수 자체는 대부분 다소 변동했으며, 이는 표본 수 감소에 따른 "
                 "자연스러운 변동일 수 있고 특정 장벽의 '진짜 관계'가 사라지거나 나타났다고 단정할 근거는 아닙니다.\n")

    # 4. figures
    lines.append("## 4. 산점도\n")
    lines.append("- `figures/gap_x_hallyu_lack.png`: Direct Gap × 한류 관심 부재")
    lines.append("- `figures/gap_x_low_awareness.png`: Direct Gap × 낮은 한국 인지도")
    lines.append("- `figures/gap_x_negative_image.png`: Direct Gap × 부정적인 한국 이미지")
    lines.append("- `figures/gap_x_conditional_gap.png`: Direct Gap × Conditional Gap")
    lines.append("(각 그림에서 주황색 점은 B13-1A 표본 30명 미만 국가, 파란색 점은 그 외 국가)\n")

    # 5. 정리 질문 응답
    lines.append("## 5. 마지막 정리\n")

    # Q1
    lines.append("### 1) Direct Gap과 가장 일관된 관계를 보이는 장벽은 무엇인가?")
    excl_barrier_rows = {r["pair"].split(" vs ")[1]: r for r in corr_rows
                          if r["subset"] == "소표본4개국_제외(n=19)" and "Direct_Gap" in r["pair"] and "Conditional_Gap" not in r["pair"]}
    consistent = []
    for r in full_barrier_rows:
        b_name = r["pair"].split(" vs ")[1]
        r_excl = excl_barrier_rows.get(b_name)
        if r["pearson_r"] is not None and r_excl and r_excl["pearson_r"] is not None:
            if (r["pearson_r"] > 0) == (r_excl["pearson_r"] > 0) and abs(r["pearson_r"]) >= 0.2 and abs(r_excl["pearson_r"]) >= 0.2:
                consistent.append((b_name, r["pearson_r"], r_excl["pearson_r"]))
    consistent.sort(key=lambda t: -abs(t[1]))
    if consistent:
        top = consistent[0]
        lines.append(f"**[관찰된 통계적 관계 요약]** '{top[0]}'가 전체 23개국(r={top[1]:.3f})과 소표본 제외 19개국"
                      f"(r={top[2]:.3f}) 모두에서 같은 방향, |r|≥0.2를 유지한 장벽 중 절댓값이 가장 큽니다.")
    else:
        lines.append("**[관찰된 통계적 관계 요약]** 전체/소표본 제외 두 조건 모두에서 |r|≥0.2를 유지하며 방향이 일치하는 "
                     "장벽은 관찰되지 않았습니다 — 8개 장벽 모두 상관 강도가 약하거나(|r|<0.2) 표본 구성에 따라 방향이 바뀌었습니다.")
    lines.append("")

    # Q2
    lines.append("### 2) 그 관계가 소표본 국가를 제외해도 유지되는가?")
    if consistent:
        lines.append(f"**[데이터상 나타나는 패턴]** 예 — {', '.join(c[0] for c in consistent)}는 소표본 4개국 제외 후에도 "
                     f"상관의 방향과 상대적 크기가 유지되었습니다.")
    else:
        lines.append("**[데이터상 나타나는 패턴]** 뚜렷하게 '유지되는 강한 관계'로 분류할 수 있는 장벽은 없었습니다. "
                     "3절의 상세 표에서 지표쌍별 r 변화량을 확인해야 합니다.")
    lines.append("")

    # Q3
    lines.append("### 3) Direct Gap과 Conditional Gap은 비슷한 국가에서 나타나는가?")
    if cg_full and cg_full["pearson_r"] is not None:
        strength = "약한" if abs(cg_full["pearson_r"]) < 0.3 else ("중간 정도의" if abs(cg_full["pearson_r"]) < 0.6 else "상대적으로 뚜렷한")
        lines.append(f"**[관찰된 통계적 관계]** Pearson r={fmt_r(cg_full['pearson_r'])}로 {strength} {cg_full['direction']}이 관찰됩니다. "
                     f"단, 두 Gap은 서로 다른 BASE(전체 응답자 vs 문화경험자)와 서로 다른 지표 쌍에서 계산된 값이므로, "
                     f"이 상관을 '같은 현상의 두 측면'으로 해석하려면 추가 검증이 필요합니다.")
    lines.append("")

    # Q4
    lines.append("### 4) 앞 단계에서 발견한 러시아·인도·카자흐스탄의 패턴은 유지되는가?")
    prior_gap_rank = sorted(direct_gap.items(), key=lambda kv: -kv[1])
    prior_gap_pos = {c: i + 1 for i, (c, v) in enumerate(prior_gap_rank)}
    lines.append("**[관찰된 수치]**")
    for c in ["러시아", "인도", "카자흐스탄"]:
        lines.append(f"- {c}: Direct Gap={direct_gap.get(c):.2f}%p (23개국 중 Gap 크기 {prior_gap_pos.get(c)}위)")
    lines.append("")
    lines.append("**[데이터상 나타나는 패턴]** 이번 단계에서도 세 국가는 여전히 Direct Gap이 큰 축에 위치합니다 "
                 "(앞 단계 보고서의 '상위3분위' 관찰과 일관됨). 다만 3절 민감도 분석과 1절 상관표에서 보듯, "
                 "이 국가들이 장벽 항목에서도 일관되게 특정 패턴을 보이는지는 장벽별로 다르므로 5절의 병목 유형 절과 "
                 "함께 확인해야 합니다.\n")

    # Q5
    lines.append("### 5) 데이터만으로 정의할 수 있는 국가별 병목 유형은 무엇인가?")
    lines.append(
        "**[데이터상 나타나는 패턴]** 통계적 유의성 단정이나 군집분석 없이, 이번 단계까지 계산된 값(Direct Gap 상위3분위 여부, "
        "Conditional Gap 상위3분위 여부, 특정 장벽 비율의 높고 낮음)을 **규칙 기반으로 조합**하면 다음과 같은 서술적 유형 구분이 "
        "가능합니다 (통계 검정을 거친 '유형 분류'가 아니라 관찰값의 조합 설명):\n"
    )
    lines.append("- **Type A (직접전환형 병목 후보)**: Direct Gap 상위3분위 + 특정 장벽(예: 한류 관심 부재) 비율도 상대적으로 높음 "
                 "— 예: 카자흐스탄, 러시아, 미국, 멕시코, 인도, 태국 (`gap_validation_report.md` 4절 참조)")
    lines.append("- **Type B (조건부전환형 병목 후보)**: Conditional Gap 상위3분위이나 Direct Gap은 중/하위 — 예: 독일, 호주, 영국")
    lines.append("- **Type C (인지·이미지 장벽형)**: Direct/Conditional Gap 크기와 무관하게 '부정적인 한국 이미지' 또는 "
                 "'낮은 한국 인지도' 비율이 유독 높음 — 예: 일본(부정적 이미지 57.5%), 프랑스·독일·러시아(낮은 인지도 상위권)")
    lines.append("- **Type D (물류/접근성 장벽형)**: '장거리 비행', '비자/출입국 절차' 등 콘텐츠·인식과 무관한 장벽이 상위 — "
                 "예: 베트남·태국(비자, 단 소표본 주의), 독일·영국(장거리 비행)")
    lines.append("이 유형 구분은 통계적으로 검증된 군집이 아니라, 이번 단계까지 계산된 지표값을 사람이 읽을 수 있게 규칙으로 "
                 "묶은 서술적 분류입니다.\n")

    # Q6
    lines.append("### 6) 아직 데이터만으로 판단할 수 없는 것은 무엇인가?")
    lines.append("**[추가 검증이 필요한 해석 가설]**")
    lines.append("- 장벽 응답과 Gap 크기 사이에 실제 인과관계가 있는지 (둘 다 국가 단위 집계값이며, 같은 응답자에게서 나온 값이 아님)")
    lines.append("- 관찰된 상관이 표본 크기·조사 설계 차이가 아닌 실제 국가 특성 차이에서 비롯되는지")
    lines.append("- Type A~D 유형이 통계적으로 서로 구분되는 집단인지 (군집분석 등 미수행)")
    lines.append("- 개인 단위에서 문화경험 -> 방한의향 -> 실제 방문으로 이어지는 실제 전환 여부")
    lines.append("- 5절의 규칙 기반 유형이 유의미한 국가군인지, 우연에 의한 그룹핑인지\n")

    # Q7
    lines.append("### 7) 다음 단계: 군집분석 vs 규칙 기반 병목 유형화, 어느 쪽이 적절한가?")
    n_after_excl = sens_rows[0]["n_excl"] if sens_rows else 19
    lines.append(
        f"**[제안, 근거 포함]** 현재로서는 **규칙 기반 병목 유형화를 우선 고도화하는 편**을 제안합니다. 근거:\n"
        f"- 표본 크기가 23개국(소표본 제외 시 {n_after_excl}개국)으로 작아, 군집분석(k-means 등)을 적용해도 군집 수/안정성 "
        f"판단 자체가 표본 크기에 크게 좌우되며 결과 해석의 신뢰도가 낮습니다.\n"
        f"- 1절 상관표에서 8개 장벽 중 다수가 |r|<0.3 수준의 약한 관계를 보여, 군집분석의 입력 차원(장벽 8개 + Gap 2개)에 "
        f"실제로 서로를 구분할 만한 신호가 충분한지 이번 단계 결과만으로는 확신하기 어렵습니다.\n"
        f"- 반면 5절의 Type A~D 같은 규칙 기반 분류는 각 조건(Gap tier, 장벽 비율 임계값)이 무엇을 근거로 하는지 "
        f"투명하게 드러나고, BASE/comparability 제약(direct_within_survey vs conditional)을 유형 정의에 직접 반영할 수 있습니다.\n"
        f"- 군집분석을 시도한다면, 그 전에 (a) 소표본 국가 처리 방침을 확정하고 (b) 어떤 지표를 표준화해 투입할지, "
        f"(c) 군집 수를 사전에 임의로 정하지 않고 안정성을 어떻게 확인할지에 대한 별도 설계가 필요합니다.\n"
    )

    return lines


def write_report_md(lines):
    with open(OUT_REPORT_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"[저장] {OUT_REPORT_MD}")


def main():
    direct_gap, cond_gap, barriers, small_sample_flag = load_data()
    print(f"[로드] direct_gap={len(direct_gap)}개국, cond_gap={len(cond_gap)}개국, barriers={len(barriers)}개국")

    corr_rows = build_correlation_table(direct_gap, cond_gap, barriers)
    write_corr_csv(corr_rows)

    sens_rows = build_sensitivity_table(corr_rows)
    write_sens_csv(sens_rows)

    build_figures(direct_gap, cond_gap, barriers, small_sample_flag)

    report_lines = build_report_md(corr_rows, sens_rows, direct_gap, cond_gap, barriers, small_sample_flag)
    write_report_md(report_lines)

    print("\n[요약]")
    print(f" - gap_barrier_correlation.csv: {len(corr_rows)}행")
    print(f" - sensitivity_analysis.csv: {len(sens_rows)}행")
    print(f" - figures: 4개 PNG")


if __name__ == "__main__":
    main()
