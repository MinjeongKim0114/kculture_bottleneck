"""
Before/After 데모: 정량 데이터만 있을 때 vs Reddit 근거를 추가했을 때 챗봇 답변 비교.

주의: reddit_candidates_for_review.csv의 relevance_status는 아직 사람이 검토하지
않았다(전부 "미검토"). 이 데모는 검토를 건너뛰고 ai_relevance_suggestion == "관련"만
가지고 진행하는 임시 실험이며, 실제 서비스에 반영하는 게 아니다. 결과를 보고
가치가 있다고 판단되면, 그때 사람이 검토를 마친 뒤 backend/app/services/chat_service.py에
정식으로 반영한다.
"""
import sys
from pathlib import Path

import pandas as pd
from openai import OpenAI

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.core.config import LLM_API_KEY, LLM_MODEL  # noqa: E402
from app.data_access.postgres_repository import PostgresDataRepository  # noqa: E402
from app.services.chat_service import SYSTEM_PROMPT, ChatService  # noqa: E402

QUESTION = (
    "미국인들은 주로 어떤 요인으로 한국을 방문하게 돼? 그리고 한국문화에 관심은 많지만 "
    "실제 방한으로 이어지지 않는 이들을 어떤 측면에서 공략해야하는지 사업적 관점에서 분석해줘."
)

REDDIT_CSV = REPO_ROOT / "data" / "processed" / "qualitative" / "reddit_candidates_for_review.csv"

REDDIT_EVIDENCE_NOTE = """
[정성적 참고자료 안내 - 주의해서 사용하세요]
아래는 Reddit에서 수집한 실제 게시물 발췌입니다. 이건 설문조사가 아니라 자기 선택
편향이 큰 온라인 커뮤니티 글이며, 아직 사람이 관련성을 최종 검토하지 않았습니다
(AI가 1차로 "관련 있어 보인다"고 제안한 것만 추림). 따라서:
- 이 자료를 %나 통계처럼 취급하지 마세요. "이런 사례가 보고된다" 정도로만 인용하세요.
- "nationality: 미확인"으로 표시된 글은 특정 국적으로 단정하지 말고 "일반적으로 보고되는
  사례"로만 인용하세요.
- 인용할 때는 반드시 출처(permalink)를 함께 제시하세요.
- 이 자료가 부족하거나 안 맞으면 억지로 쓰지 말고 무시하세요.
"""


def build_reddit_evidence(limit_attributed: int = 5, limit_general: int = 5) -> str:
    df = pd.read_csv(REDDIT_CSV, encoding="utf-8-sig")
    relevant = df[
        (df["ai_relevance_suggestion"] == "관련")
        & (df["barrier_category"].isin(["institutional_language", "economic_physical_access"]))
    ]
    attributed = relevant[relevant["nationality_mentions_guess"].fillna("").str.contains("american", case=False)]
    general = relevant[relevant["nationality_mentions_guess"].fillna("") == ""]

    lines = [REDDIT_EVIDENCE_NOTE, "\n[수집된 게시물 발췌]"]
    for _, r in attributed.head(limit_attributed).iterrows():
        lines.append(
            f"- (nationality: 미국 언급) [{r['barrier_category']}] \"{r['title']}\" - "
            f"{str(r['selftext'])[:300]}... (출처: {r['permalink']})"
        )
    for _, r in general.head(limit_general).iterrows():
        lines.append(
            f"- (nationality: 미확인) [{r['barrier_category']}] \"{r['title']}\" - "
            f"{str(r['selftext'])[:300]}... (출처: {r['permalink']})"
        )
    return "\n".join(lines)


def main():
    repo = PostgresDataRepository()
    service = ChatService(repo)
    client = OpenAI(api_key=LLM_API_KEY)

    quant_context = service._build_context()

    print("=" * 80)
    print("BEFORE (정량 데이터만)")
    print("=" * 80)
    before = client.chat.completions.create(
        model=LLM_MODEL, temperature=0, seed=42,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"[데이터]\n{quant_context}\n\n[질문]\n{QUESTION}"},
        ],
    )
    print(before.choices[0].message.content)

    reddit_evidence = build_reddit_evidence()

    print("\n" + "=" * 80)
    print("AFTER (정량 + Reddit, 검토 전 데이터로 진행하는 임시 실험)")
    print("=" * 80)
    after = client.chat.completions.create(
        model=LLM_MODEL, temperature=0, seed=42,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"[데이터]\n{quant_context}\n\n{reddit_evidence}\n\n[질문]\n{QUESTION}",
            },
        ],
    )
    print(after.choices[0].message.content)


if __name__ == "__main__":
    main()
