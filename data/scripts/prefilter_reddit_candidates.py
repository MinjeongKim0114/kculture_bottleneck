"""
reddit_candidates.csv 1차 필터링 - 사람 검토 부담을 줄이기 위한 전처리.

이 스크립트는 관련성을 "확정"하지 않는다. 최종 판정은 항상 사람이 한다
(final_analysis_framework.md의 "값을 추정/확정하지 않는다" 원칙과 동일).
이 스크립트가 하는 일은 두 가지뿐이다:

1. 기계적으로 확실한 것만 자동 처리
   - 중복 게시물(같은 post_id가 여러 검색어에 걸린 경우) 병합
   - 완전히 빈 글/삭제된 글은 "명백히_무관"으로 분리 (검토 대상에서 제외하되 삭제하지 않음)
2. 나머지에 대해 GPT-4o-mini로 "1차 판정 제안"만 붙인다 (ai_relevance_suggestion,
   ai_relevance_reason) - relevance_status는 여전히 "미검토"로 남긴다. 사람이 이
   제안을 참고해서 빠르게 훑어보되, 최종 확정은 사람이 relevance_status에 직접 써야 한다.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import pandas as pd
from openai import OpenAI

REPO_ROOT = Path(__file__).resolve().parents[2]
IN_CSV = REPO_ROOT / "data" / "processed" / "qualitative" / "reddit_candidates.csv"
OUT_REVIEW_CSV = REPO_ROOT / "data" / "processed" / "qualitative" / "reddit_candidates_for_review.csv"
OUT_EXCLUDED_CSV = REPO_ROOT / "data" / "processed" / "qualitative" / "reddit_candidates_auto_excluded.csv"

BACKEND_ENV = REPO_ROOT / "backend" / ".env"

BATCH_SIZE = 10
MODEL = "gpt-4o-mini"

SYSTEM_PROMPT = """당신은 리서치 보조입니다. 아래 각 Reddit 게시물이, 주어진 "장벽 카테고리"에
실제로 관련된 구체적 경험/의견을 담고 있는지 판정하세요.

관련 = 그 장벽(언어소통/비자/여행경비/장거리비행/할랄음식·종교환경 등)에 대한 실제 불만,
경험, 구체적 설명이 담긴 경우
무관 = 검색어와 우연히 단어만 겹칠 뿐 실제 내용은 다른 주제인 경우
애매 = 관련이 있어 보이지만 확신이 안 서는 경우

당신의 판정은 참고용 제안일 뿐이며, 최종 확정은 사람이 합니다. 모르면 "애매"를 선택하세요.
반드시 JSON 배열로만 응답하세요: [{"index": 0, "relevance": "관련"|"무관"|"애매", "reason": "한 문장"}, ...]
"""


def load_dotenv_key() -> str:
    if BACKEND_ENV.exists():
        for line in BACKEND_ENV.read_text(encoding="utf-8").splitlines():
            if line.startswith("LLM_API_KEY="):
                return line.split("=", 1)[1].strip()
    raise RuntimeError("backend/.env 에서 LLM_API_KEY를 찾지 못함")


def dedupe(df: pd.DataFrame) -> pd.DataFrame:
    """같은 post_id가 여러 (barrier_category, query, subreddit) 조합에서 잡힌 경우,
    첫 등장 행을 기준으로 남기고 매칭된 barrier_category 전부를 한 컬럼에 모은다."""
    matched = (
        df.groupby("post_id")["barrier_category"]
        .apply(lambda s: ";".join(sorted(set(s))))
        .rename("all_matched_barrier_categories")
    )
    first = df.drop_duplicates(subset="post_id", keep="first").set_index("post_id")
    first = first.join(matched)
    return first.reset_index()


def split_auto_excluded(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    selftext = df["selftext"].fillna("")
    is_removed = selftext.str.contains(r"\[deleted\]|\[removed\]", case=False, na=False)
    is_too_short = selftext.str.len() < 20
    auto_exclude_mask = is_removed | is_too_short

    excluded = df[auto_exclude_mask].copy()
    excluded["auto_exclude_reason"] = [
        "삭제/제거된 게시물" if r else "본문이 20자 미만 (내용 없음)"
        for r in is_removed[auto_exclude_mask]
    ]
    remaining = df[~auto_exclude_mask].copy()
    return remaining, excluded


def classify_batch(client: OpenAI, rows: list[dict]) -> dict[int, dict]:
    items = []
    for i, r in enumerate(rows):
        items.append({
            "index": i,
            "barrier_category": r["barrier_category"],
            "matched_query": r["matched_query"],
            "title": r.get("title", "") or "",
            "selftext_excerpt": (r.get("selftext", "") or "")[:600],
        })
    resp = client.chat.completions.create(
        model=MODEL,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps({"items": items}, ensure_ascii=False)},
        ],
    )
    content = resp.choices[0].message.content
    try:
        parsed = json.loads(content)
        results = parsed if isinstance(parsed, list) else parsed.get("results") or parsed.get("items") or []
    except (json.JSONDecodeError, AttributeError):
        print("  경고: 배치 응답 파싱 실패, 이 배치는 전부 '애매'로 표시")
        return {i: {"relevance": "애매", "reason": "AI 응답 파싱 실패"} for i in range(len(rows))}

    out = {}
    for item in results:
        idx = item.get("index")
        if idx is not None:
            out[idx] = {"relevance": item.get("relevance", "애매"), "reason": item.get("reason", "")}
    for i in range(len(rows)):
        out.setdefault(i, {"relevance": "애매", "reason": "AI가 응답하지 않음"})
    return out


def main():
    df = pd.read_csv(IN_CSV, encoding="utf-8-sig")
    print(f"원본: {len(df)}건")

    df = dedupe(df)
    print(f"중복 제거 후: {len(df)}건 (post_id 기준 고유)")

    remaining, excluded = split_auto_excluded(df)
    print(f"명백히 무관(자동 제외): {len(excluded)}건")
    print(f"AI 1차 판정 대상: {len(remaining)}건")

    excluded.to_csv(OUT_EXCLUDED_CSV, index=False, encoding="utf-8-sig")

    api_key = load_dotenv_key()
    client = OpenAI(api_key=api_key)

    remaining = remaining.reset_index(drop=True)
    ai_relevance = [None] * len(remaining)
    ai_reason = [None] * len(remaining)

    rows = remaining.to_dict("records")
    for start in range(0, len(rows), BATCH_SIZE):
        batch = rows[start:start + BATCH_SIZE]
        print(f"  분류 중 {start+1}~{start+len(batch)}/{len(rows)}")
        try:
            results = classify_batch(client, batch)
        except Exception as e:
            print(f"  배치 실패: {e}, 이 배치는 '애매'로 표시")
            results = {i: {"relevance": "애매", "reason": f"API 오류: {e}"} for i in range(len(batch))}
        for i, res in results.items():
            ai_relevance[start + i] = res["relevance"]
            ai_reason[start + i] = res["reason"]
        time.sleep(0.5)

    remaining["ai_relevance_suggestion"] = ai_relevance
    remaining["ai_relevance_reason"] = ai_reason
    # relevance_status는 사람이 최종 확정하는 컬럼 - AI 제안과 분리, 절대 자동으로 채우지 않음
    remaining["relevance_status"] = "미검토"

    remaining = remaining.sort_values(
        by="ai_relevance_suggestion",
        key=lambda s: s.map({"관련": 0, "애매": 1, "무관": 2}),
    )
    remaining.to_csv(OUT_REVIEW_CSV, index=False, encoding="utf-8-sig")

    print(f"\n저장: {OUT_REVIEW_CSV} ({len(remaining)}건, AI 제안 '관련'부터 정렬됨)")
    print(f"저장: {OUT_EXCLUDED_CSV} ({len(excluded)}건, 자동 제외 - 검토 안 해도 됨)")
    print("\nAI 제안 분포:")
    print(remaining["ai_relevance_suggestion"].value_counts())
    print("\n다음 단계: reddit_candidates_for_review.csv를 열어서 relevance_status 컬럼을")
    print("사람이 직접 채우세요. ai_relevance_suggestion은 참고용일 뿐 확정이 아닙니다.")


if __name__ == "__main__":
    main()
