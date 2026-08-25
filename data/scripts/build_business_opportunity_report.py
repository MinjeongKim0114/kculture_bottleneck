"""
reddit_candidates_business_classified.csv를 사업 기회 테마별로 묶어서 사람이 읽을
보고서(markdown)로 만든다. AI가 자유 텍스트로 붙인 business_theme은 표현이 제각각
(예: "여행 정보 제공" vs "여행 정보 공유")이라, 여기서 의미 단위로 묶는다.

이 스크립트는 최종 결론을 내리지 않는다 - 테마별로 몇 건이 있고 어떤 실제 발언들이
있는지 근거(permalink 포함)와 함께 정리만 한다. 최종 사업 판단은 사람이 한다
(final_analysis_framework.md 0절: 우선순위는 근거 데이터에 기반해야 하며 "감"으로
결정하지 않는다는 원칙을 정성 데이터에도 동일하게 적용).
"""
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
IN_CSV = REPO_ROOT / "data" / "processed" / "qualitative" / "reddit_candidates_business_classified.csv"
OUT_MD = REPO_ROOT / "data" / "processed" / "qualitative" / "business_opportunity_themes.md"

# 자유 텍스트 business_theme -> 클러스터 라벨. 표현만 다를 뿐 같은 주제인 것들을 묶는다.
THEME_CLUSTERS = {
    "여행 정보/일정 큐레이션": [
        "여행 정보 제공", "여행 정보 공유", "관광 정보 제공", "여행 일정 계획 서비스",
        "여행 계획 서비스", "여행 계획 컨설팅", "여행 일정 조정 서비스", "여행 경험 공유",
        "가족 여행 정보 제공", "한국 여행 정보 제공", "여행 일정 추천 서비스",
    ],
    "비자/이주 컨설팅": [
        "비자 상담 서비스", "비자 신청 지원 서비스", "관광 비자 컨설팅", "이주 컨설팅",
        "관광 비자 정보", "비자 컨설팅",
    ],
    "유학 컨설팅": ["유학 상담 서비스", "유학 컨설팅"],
    "할랄푸드 정보/큐레이션": ["할랄푸드 정보 큐레이션", "할랄 음식 정보"],
    "외국인 대상 통신(SIM/디지털 인프라)": ["외국인 대상 통신(SIM)"],
    "의료/헬스케어 통역·안내": ["의료 통역 서비스", "의료 관광"],
}


def cluster_of(theme: str) -> str | None:
    for cluster, members in THEME_CLUSTERS.items():
        if theme in members:
            return cluster
    return None


def main():
    df = pd.read_csv(IN_CSV, encoding="utf-8-sig")
    df = df[df["population_type"] != "무관"].copy()
    df["theme_cluster"] = df["business_theme"].apply(cluster_of)

    lines = [
        "# Reddit 기반 사업 기회 테마 요약 (Track 2 — 체류/방문 외국인 페인포인트)",
        "",
        "**주의 (반드시 읽을 것)**:",
        "- 이 문서는 Reddit이라는 자기 선택 편향이 큰 영어권 온라인 커뮤니티에서 수집한 자료입니다.",
        "  23개국 설문(잠재방한객조사)과는 **완전히 다른 모집단**이며, 통계적으로 대표성이 없습니다.",
        "- population_type/business_theme은 AI(gpt-4o-mini)의 1차 판정이며, 사람이 최종 확인하지 않았습니다.",
        "- \"몇 건\"이라는 숫자는 설문 %처럼 취급하면 안 됩니다 — 이건 %가 아니라 \"이런 목소리가",
        "  관찰된다\"는 정성적 신호일 뿐입니다.",
        "- 목적은 신사업 기획의 아이디어/가설을 근거와 함께 제공하는 것이며, 최종 사업 판단은",
        "  사람이 합니다.",
        "",
    ]

    for cluster in THEME_CLUSTERS:
        sub = df[df["theme_cluster"] == cluster]
        if sub.empty:
            continue
        lines.append(f"## {cluster} ({len(sub)}건)")
        lines.append("")
        pop_counts = sub["population_type"].value_counts()
        lines.append("**대상**: " + ", ".join(f"{k} {v}건" for k, v in pop_counts.items()))
        lines.append("")
        lines.append("**구조적 겹침 여부**: " + (
            "잠재방문객과 체류거주외국인 모두에서 관찰됨 - 단기 방문객에게도 영향 줄 가능성 있음"
            if pop_counts.get("둘다해당(구조적)", 0) > 0 or (
                pop_counts.get("잠재방문객", 0) > 0 and pop_counts.get("체류거주외국인", 0) > 0
            ) else "한쪽 그룹에서만 관찰됨"
        ))
        lines.append("")
        lines.append("**대표 사례**:")
        for _, r in sub.head(5).iterrows():
            title = str(r["title"]).replace("\n", " ")[:100]
            reason = str(r.get("business_theme_reason", "") or "")
            lines.append(f"- [{r['population_type']}] \"{title}\" — {reason} (출처: {r['permalink']})")
        lines.append("")

    # 클러스터에 안 묶인 나머지도 개수만 참고로 남긴다 (버리지 않음)
    unclustered = df[df["theme_cluster"].isna() & (df["business_theme"].fillna("") != "")]
    lines.append(f"## 기타 (클러스터로 안 묶인 개별 테마, {len(unclustered)}건)")
    lines.append("")
    lines.append("아래는 1~3건씩만 나온 소수 테마들입니다 (참고용, 세부 검토 안 함):")
    lines.append("")
    for theme, cnt in unclustered["business_theme"].value_counts().head(15).items():
        lines.append(f"- {theme} ({cnt}건)")

    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(f"저장: {OUT_MD}")
    print(f"클러스터링된 건수: {len(df[df['theme_cluster'].notna()])}/{len(df)}")


if __name__ == "__main__":
    main()
