"""
Reddit 후보군 전체(942건)를 "관광 장벽 매칭" 기준이 아니라, 이 프로젝트의 실제 핵심
질문 기준으로 재분류한다:

"어떻게 하면 감에 의존한 기획에서 벗어나, 국가별 실제 수요와 한국에 대한 인식의
간극을 데이터로 발견하고 새로운 사업 기회로 연결할 수 있을까?"
(final_analysis_framework.md 0절)

기존 분류(ai_relevance_suggestion)는 "설문의 8개 방문 장벽과 매칭되는가"만 봤는데,
실제로 읽어보니 대부분 무관 판정된 글들이 "체류/거주 외국인의 페인포인트"였고, 이것도
그 자체로 사업 기회 신호일 수 있다는 게 확인됐다 (설문 데이터와는 별개 트랙으로 취급).

두 축으로 분류한다 (기존 컬럼은 삭제하지 않고 새 컬럼만 추가):
- population_type: 잠재방문객 / 체류거주외국인 / 둘다해당(구조적) / 무관
  "둘다해당(구조적)"은 거주자 얘기처럼 보이지만 단기 방문객도 똑같이 겪을 수 있는
  구조적 문제(예: ARC 없으면 배달앱/SIM/결제 불가, 할랄 음식 정보 부족)를 뜻한다.
- business_theme: 사업 기회로 연결될 만한 주제 자유 텍스트 (없으면 빈 문자열)

이것도 최종 판정이 아니라 AI 1차 제안이다. 사람이 최종 검토해야 한다.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import pandas as pd
from openai import OpenAI
import os

REPO_ROOT = Path(__file__).resolve().parents[2]
IN_CSV = REPO_ROOT / "data" / "processed" / "qualitative" / "reddit_candidates_for_review.csv"
ALL_CSV = REPO_ROOT / "data" / "processed" / "qualitative" / "reddit_candidates.csv"
OUT_CSV = REPO_ROOT / "data" / "processed" / "qualitative" / "reddit_candidates_business_classified.csv"
BACKEND_ENV = REPO_ROOT / "backend" / ".env"

BATCH_SIZE = 8
MODEL = "gpt-5.6-terra"

SYSTEM_PROMPT = """당신은 사업 기회 발굴을 위한 리서치 보조입니다. 목표는 "관광 장벽과
정확히 매칭되는가"가 아니라 "이 글이 한국 관련 신사업 기획에 참고할 만한 실제 페인포인트/
니즈를 담고 있는가"입니다.

각 게시물에 대해 두 가지를 판단하세요:

1. population_type — 판단 기준은 **화자가 물리적으로 한국에 있었는지가 아니라, 그
   사람의 체류 목적·기간 의도**입니다:
   - "잠재방문객": 짧은 관광/여행이 목적. 아직 안 가봤어도 되고, 이미 짧게 다녀왔어도
     됨. 핵심은 "단기 방문"이라는 의도.
   - "체류거주외국인": 유학(학위과정/어학연수 포함), 취업, 이주, 결혼이민 등 **장기
     체류가 목적**. 아직 한국에 도착 전이거나 합격/지원 단계여도, 목적이 장기체류면
     이쪽입니다. (예: "경희대 합격했는데 갈지 고민" → 아직 안 갔어도 체류거주외국인.
     "겨울 프로그램 비자 문의" → 체류거주외국인. "다음 달 3주 여행 계획" → 잠재방문객.)
   - "둘다해당(구조적)": 화자는 거주자/유학생이지만, 그 문제가 단기 방문객도 똑같이
     겪을 수 있는 구조적 문제(예: ARC 없으면 결제/배달앱 사용 불가, 할랄 음식 정보
     부족, 언어 때문에 병원 이용 어려움, 지도 앱 영어 지원 부족)인 경우
   - "무관": 사업 기회와 무관한 잡담/개인사/한국과 무관한 내용

   주의: 단어만 보고 기계적으로 판단하지 마세요("university"가 있다고 무조건 거주자는
   아님 — "한국 대학 유학 갈지 말지 고민" 같은 진로 상담이 아니라, 이미 다녀온 여행
   중 우연히 대학교를 지나간 얘기라면 잠재방문객일 수 있음). 글 전체 맥락에서 화자가
   실제로 무엇을 하려는지/했는지를 읽고 판단하세요.

   중요 — 화자 본인 vs 글 속에 언급된 제3자를 혼동하지 마세요: "이미 여행했거나 현재
   살고 있는 분들께 묻습니다" 같은 문장은 화자가 아니라 "답변해줄 대상(청자)"을
   가리키는 경우가 많습니다. population_type은 오직 **화자 본인**의 체류 목적·의도만
   근거로 판단하세요. 글에 "거주자"라는 단어가 보인다고 해서 자동으로 "둘다해당(구조적)"
   이나 "체류거주외국인"으로 분류하지 마세요 — 화자 본인이 실제로 거주자/유학생인지
   먼저 확인한 뒤, 그 문제가 단기 방문객에게도 똑같이 적용되는 구조적 문제일 때만
   "둘다해당(구조적)"입니다.

2. business_theme: 이 글에서 읽히는 사업 기회 주제를 한국어 짧은 명사구로 (예:
   "외국인 대상 핀테크/결제", "할랄푸드 정보 큐레이션", "의료 통역 서비스", "관광 비자
   컨설팅", "외국인 대상 통신(SIM)" 등). 사업 기회로 연결할 거리가 전혀 없으면 빈 문자열.

   다음 두 경우는 business_theme을 비워두세요:
   - 단순 과거 회고/추억담일 뿐, 지금도 유효한 실제 니즈나 불편이 아닌 경우 (예: "예전에
     이 동네 살았는데 그때는 이랬다"는 회상 — 현재 사업 기회로 연결할 근거가 아님)
   - 한국이 글의 핵심이 아니라 배경으로 스쳐 지나가듯 언급될 뿐인 경우 (예: 화자가
     이미 한국을 떠나 다른 나라에 살며 그 나라 관련 팁을 묻는데 한국은 "예전에 살았던
     곳"으로만 언급되는 경우 — 한국 관련 니즈/불편이 글의 실제 주제가 아님)

반드시 JSON으로만 응답: {"results": [{"index": 0, "population_type": "...",
"business_theme": "...", "reason": "한 문장(화자의 목적/의도를 근거로 설명)"}, ...]}
"""


def load_dotenv_key() -> str:
    value = os.environ.get("LLM_API_KEY")

    if value:
        return value

    if BACKEND_ENV.exists():
        for line in BACKEND_ENV.read_text(encoding="utf-8").splitlines():
            if line.startswith("LLM_API_KEY="):
                return line.split("=", 1)[1].strip()

    raise RuntimeError("LLM_API_KEY 없음")

def classify_batch(client: OpenAI, rows: list[dict]) -> dict[int, dict]:
    items = [
        {
            "index": i,
            "title": r.get("title", "") or "",
            "selftext_excerpt": (r.get("selftext", "") or "")[:500],
        }
        for i, r in enumerate(rows)
    ]
    resp = client.chat.completions.create(
        model=MODEL, response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps({"items": items}, ensure_ascii=False)},
        ],
    )
    try:
        parsed = json.loads(resp.choices[0].message.content)
        results = parsed.get("results", [])
    except (json.JSONDecodeError, AttributeError):
        return {i: {"population_type": "무관", "business_theme": "", "reason": "파싱 실패"} for i in range(len(rows))}

    out = {}
    for item in results:
        idx = item.get("index")
        if idx is not None:
            out[idx] = {
                "population_type": item.get("population_type", "무관"),
                "business_theme": item.get("business_theme", ""),
                "reason": item.get("reason", ""),
            }
    for i in range(len(rows)):
        out.setdefault(i, {"population_type": "무관", "business_theme": "", "reason": "응답 없음"})
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--full", action="store_true",
        help="이미 분류된 post_id까지 전부 다시 분류(프롬프트를 고쳤을 때만 사용). "
             "기본값은 신규 post_id만 분류하고 기존 라벨(사람이 검증한 것 포함)은 보존.",
    )
    args = parser.parse_args()

    df = pd.read_csv(IN_CSV, encoding="utf-8-sig").reset_index(drop=True)
    print(f"reddit_candidates_for_review.csv 전체: {len(df)}건")

    existing = pd.DataFrame()
    if not args.full and OUT_CSV.exists():
        existing = pd.read_csv(OUT_CSV, encoding="utf-8-sig")
        already_done = set(existing["post_id"])
        df = df[~df["post_id"].isin(already_done)].reset_index(drop=True)
        print(f"기존 분류 보존: {len(already_done)}건 (건드리지 않음)")

    print(f"이번에 분류할 건수: {len(df)}건")
    if df.empty:
        print("신규 분류 대상 없음 - 종료")
        return

    api_key = load_dotenv_key()
    client = OpenAI(api_key=api_key)

    rows = df.to_dict("records")
    pop_types, themes, reasons = [None] * len(rows), [None] * len(rows), [None] * len(rows)

    for start in range(0, len(rows), BATCH_SIZE):
        batch = rows[start:start + BATCH_SIZE]
        print(f"  분류 중 {start+1}~{start+len(batch)}/{len(rows)}")
        try:
            results = classify_batch(client, batch)
        except Exception as e:
            print(f"  배치 실패: {e}")
            results = {i: {"population_type": "무관", "business_theme": "", "reason": f"오류: {e}"} for i in range(len(batch))}
        for i, res in results.items():
            pop_types[start + i] = res["population_type"]
            themes[start + i] = res["business_theme"]
            reasons[start + i] = res["reason"]
        time.sleep(0.4)

    df["population_type"] = pop_types
    df["business_theme"] = themes
    df["business_theme_reason"] = reasons

    combined = pd.concat([existing, df], ignore_index=True) if not existing.empty else df
    combined.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")

    print(f"\n저장: {OUT_CSV} (총 {len(combined)}건, 이번에 신규/재분류 {len(df)}건)")
    print("\npopulation_type 분포(전체):")
    print(combined["population_type"].value_counts())
    print("\nbusiness_theme 상위 20개 (빈 값 제외, 전체):")
    print(combined[combined["business_theme"].fillna("") != ""]["business_theme"].value_counts().head(20))


if __name__ == "__main__":
    main()
