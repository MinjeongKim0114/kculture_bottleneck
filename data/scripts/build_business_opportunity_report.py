"""
reddit_candidates_business_classified.csv를 사람이 읽을 보고서(markdown)로 만든다.

이전에는 business_theme 자유 텍스트를 고정된 THEME_CLUSTERS 딕셔너리로 묶었는데,
분류 모델이 더 정확해질수록(gpt-5.6-terra) 테마 표현이 세분화되면서 고정 문자열
매칭이 거의 안 먹혔다(클러스터링률 120/770 -> 6/668). 억지로 묶기보다 개별 항목을
population_type별로 그대로 나열하는 쪽이 정보 손실이 없다고 판단해 클러스터링을
없앴다 — 실시간 질문별 검색은 chat_service.py의 pgvector 유사도 검색이 대신한다.

이 스크립트는 최종 결론을 내리지 않는다 - 어떤 실제 발언들이 있는지 근거(permalink
포함)와 함께 정리만 한다. 최종 사업 판단은 사람이 한다 (final_analysis_framework.md
0절: 우선순위는 근거 데이터에 기반해야 하며 "감"으로 결정하지 않는다는 원칙을
정성 데이터에도 동일하게 적용).
"""
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
IN_CSV = REPO_ROOT / "data" / "processed" / "qualitative" / "reddit_candidates_business_classified.csv"
OUT_MD = REPO_ROOT / "data" / "processed" / "qualitative" / "business_opportunity_themes.md"

POPULATION_ORDER = ["둘다해당(구조적)", "잠재방문객", "체류거주외국인"]


def main():
    df = pd.read_csv(IN_CSV, encoding="utf-8-sig")
    df = df[df["population_type"] != "무관"].copy()
    df = df[df["business_theme"].fillna("") != ""].copy()
    # business_theme으로 정렬해두면 표현이 비슷한 항목끼리 자연스럽게 옆에 붙는다
    # (강제로 묶지는 않되, 읽을 때 편의를 위한 정렬일 뿐).
    df = df.sort_values(["population_type", "business_theme"])

    lines = [
        "# Reddit 기반 사업 기회 아이디어 목록 (Track 2 — 체류/방문 외국인 페인포인트)",
        "",
        "**주의 (반드시 읽을 것)**:",
        "- 이 문서는 Reddit이라는 자기 선택 편향이 큰 영어권 온라인 커뮤니티에서 수집한 자료입니다.",
        "  23개국 설문(잠재방한객조사)과는 **완전히 다른 모집단**이며, 통계적으로 대표성이 없습니다.",
        "- population_type/business_theme은 AI(gpt-5.6-terra)의 1차 판정이며, 사람이 최종 확인하지 않았습니다.",
        "- 예전 버전과 달리 테마를 고정 카테고리로 묶지 않고 **개별 항목을 그대로 나열**합니다.",
        "  요약 집계가 필요 없는 대신, 정보 손실 없이 원문 그대로 검토할 수 있습니다.",
        "- 챗봇(`POST /api/chat`)은 이 문서와 별개로, 질문마다 pgvector 유사도 검색으로",
        "  관련 사례를 그때그때 찾아 씁니다(`data/scripts/generate_reddit_embeddings.py` 참고).",
        "- 목적은 신사업 기획의 아이디어를 근거와 함께 제공하는 것이며, 최종 사업 판단은",
        "  사람이 합니다.",
        "",
        f"총 {len(df)}건 (population_type != '무관', business_theme 있음)",
        "",
    ]

    for pop in POPULATION_ORDER:
        sub = df[df["population_type"] == pop]
        if sub.empty:
            continue
        lines.append(f"## {pop} ({len(sub)}건)")
        lines.append("")
        for _, r in sub.iterrows():
            title = str(r["title"]).replace("\n", " ")[:100]
            reason = str(r.get("business_theme_reason", "") or "")
            lines.append(
                f"- **{r['business_theme']}** — \"{title}\" — {reason} "
                f"(출처: {r['permalink']})"
            )
        lines.append("")

    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(f"저장: {OUT_MD}")
    print(f"총 {len(df)}건 (population_type != '무관', business_theme 있음)")


if __name__ == "__main__":
    main()
