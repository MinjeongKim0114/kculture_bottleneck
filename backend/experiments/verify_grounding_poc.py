"""실험용 스크립트 — 방법 1(구조화된 인용/citation) 검증 로직 PoC.

chat_service.py는 전혀 건드리지 않는다. 실제 DB의 potential_tourist_2025_survey
데이터를 그대로 재사용해서, 모델이 이 데이터를 인용할 때 country/topic/item/value를
구조화된 citations 배열로 같이 내놓게 하고, 그 citation이 실제 DB 값과 정확히
일치하는지 코드로 대조한다.

목적: 이 방식이 실제로 오늘 겪은 두 종류의 환각(완전 창작형, 합성형)을 잡아내는지
라이브로 확인하고, 결과를 보고 원본(chat_service.py)에 반영할지 결정하기 위함.

실행: cd backend && py experiments/verify_grounding_poc.py
결과: 콘솔에도 출력하지만, 한글 콘솔 인코딩 문제를 피하기 위해
      backend/experiments/_poc_result.json 에도 그대로 저장한다.
"""
import json
import re
from collections import defaultdict
from pathlib import Path

import psycopg
from openai import OpenAI
from psycopg.rows import dict_row

from app.core.config import DATABASE_URL, LLM_API_KEY, LLM_MODEL
from app.data_access.postgres_repository import PostgresDataRepository
from app.services.chat_service import ChatService, SYSTEM_PROMPT

RESULT_FILE = Path(__file__).parent / "_poc_result.json"

# 1차 실험(exact match)에서 드러난 문제:
# (1) 모델이 긴 item 라벨을 줄여 쓰면(예: "...- 전문 가이드 동반" -> "전문 가이드 동반")
#     값은 맞는데도 문자열이 100% 안 맞아 오탐이 남 -> 정규화 후 부분일치로 완화.
# (2) 원본 데이터 자체에 동일 (topic="nan", item) 키에 서로 다른 값이 중복 존재함
#     (OCR 추출 과정에서 topic이 비어버린 행들이 섞임) -> 키 하나에 값 하나만 담던
#     dict를 후보 리스트로 바꿔서, 후보 중 하나와만 맞아도 통과시킨다.
_PUNCT_RE = re.compile(r"[\s/\-·,()]+")


def normalize(text: str) -> str:
    return _PUNCT_RE.sub("", text or "")

# 기존 규칙 18(순수 answer+follow_up_questions JSON)을 이 실험에서만 대체한다.
# citations는 [2025 잠재방한여행객조사] 블록에서 인용한 수치에 한해서만 채우게 한다 -
# 이 블록이 오늘 두 사고(완전 창작형, 합성형)의 실제 발생 지점이었기 때문에 범위를
# 좁혀서 검증 개념 자체가 통하는지부터 확인한다.
CITATION_ADDENDUM = """
[실험용 추가 규칙 — 위 18번 규칙의 출력 형식을 아래로 대체합니다]
반드시 이 JSON 형식으로만 응답하세요:
{"answer": "<답변 본문>", "follow_up_questions": ["...", ...],
 "citations": [{"country": "국가명", "topic": "topic 필드 원문", "item": "item 필드 원문", "value": 12.3}]}

citations 배열 규칙:
- [2025 잠재방한여행객조사] 블록에서 인용한 수치마다, 그 값이 나온 country/topic/item을
  그 블록에 있는 원문 그대로 정확히 옮겨 적으세요. 요약하거나 바꿔 쓰지 마세요.
- 그 블록에서 인용한 게 아니라면(다른 데이터 출처) citations에 넣지 마세요.
- [2025 잠재방한여행객조사] 블록을 전혀 인용하지 않았다면 citations는 빈 배열로 두세요.
- 근사치·추정치·요약값을 citations에 넣지 말고, 실제 그 블록의 행 값 그대로만 넣으세요.
"""


def build_lookup(countries: list[str]) -> dict[str, list[dict]]:
    """country -> [{item, item_norm, topic, value}, ...] 후보 리스트를 만든다.

    topic은 참고용으로만 들고 있고 매칭 조건에서는 뺀다 - 같은 조사 안에서도
    topic 라벨 표기가 항목마다 미묘하게 다르거나(예: "(~2028년)" 유무) 아예
    비어있는(topic="nan") 행이 섞여 있어, topic을 강하게 요구하면 진짜 인용도
    오탐 처리되는 문제가 있었다.
    """
    with psycopg.connect(DATABASE_URL, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT segment, topic, item, value FROM potential_tourist_2025_survey "
                "WHERE \"group\" = '거주국별' AND segment = ANY(%s)",
                (countries,),
            )
            rows = cur.fetchall()
    lookup: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        lookup[r["segment"]].append(
            {"item": r["item"], "item_norm": normalize(r["item"]), "topic": r["topic"], "value": r["value"]}
        )
    return lookup


def verify_citations(
    citations: list[dict], lookup: dict[str, list[dict]], tol: float = 0.05
) -> list[dict]:
    """각 citation의 item을 정규화 후 부분일치로 후보를 찾고, 후보 중 하나라도
    값이 일치하면 통과시킨다. 후보가 아예 없으면 '없음', 후보는 있는데 값이
    전부 다르면 '값 불일치'로 구분해서 보고한다."""
    problems = []
    for c in citations:
        candidates = lookup.get(c.get("country"), [])
        cited_norm = normalize(c.get("item", ""))
        matches = [
            cand for cand in candidates
            if cited_norm and (cited_norm in cand["item_norm"] or cand["item_norm"] in cited_norm)
        ]
        if not matches:
            problems.append({"citation": c, "reason": "이 country/item과 유사한 항목이 데이터에 없음"})
            continue
        try:
            cited_value = float(c.get("value"))
        except (TypeError, ValueError):
            problems.append({"citation": c, "reason": f"value가 숫자가 아님: {c.get('value')!r}"})
            continue
        if not any(abs(m["value"] - cited_value) <= tol for m in matches):
            candidate_values = [m["value"] for m in matches]
            problems.append(
                {"citation": c, "reason": f"값 불일치 (후보 값들: {candidate_values}, 인용: {cited_value})"}
            )
    return problems


def ask_with_citations(svc: ChatService, client: OpenAI, question: str) -> dict:
    """ChatService의 실제 컨텍스트 조립 로직을 그대로 재사용하되, 응답 형식만
    실험용 citations 포함 형식으로 바꿔서 호출한다."""
    data_context = svc._build_context()
    qualitative = svc._build_qualitative_context(question)
    survey = svc._build_2025_survey_context(question)
    content = (
        f"[데이터]\n{data_context}\n\n{qualitative}\n\n{survey}\n\n[질문]\n{question}"
    )
    response = client.chat.completions.create(
        model=LLM_MODEL,
        seed=42,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT + CITATION_ADDENDUM},
            {"role": "user", "content": content},
        ],
    )
    return json.loads(response.choices[0].message.content)


TEST_CASES = [
    {
        "label": "A. 정상 케이스 — UAE 인지도 질문 (실제 2025년 조사 데이터로 답변 가능)",
        "question": "UAE 사람들이 해외여행 목적지로서 한국을 얼마나 알고 있어? 2025년 조사 기준으로 알려줘.",
        "countries_for_lookup": ["아랍에미리트", "UAE"],
    },
    {
        "label": "B. 사고 재현 — UAE 패키지·단기투어 서비스 선호 (합성형 환각이 나왔던 주제)",
        "question": "UAE 방한 의향자들이 패키지·단기투어 상품에서 원하는 서비스와 그 비율을 2025년 조사 기준으로 알려줘.",
        "countries_for_lookup": ["아랍에미리트", "UAE"],
    },
    {
        "label": "C. 사고 재현 — 사우디아라비아 (완전 창작형 환각이 나왔던 국가)",
        "question": "사우디아라비아의 방한 장벽을 2025년 조사 기준으로 자세히 알려줘.",
        "countries_for_lookup": ["사우디아라비아"],
    },
]


def run_sanity_check() -> dict:
    """느슨해진 매칭이 '진짜 지어낸 값'까지 통과시켜버리진 않는지 직접 확인한다
    (LLM 호출 없이, verify_citations만 수동으로 테스트)."""
    lookup = build_lookup(["아랍에미리트", "UAE"])
    fake_citations = [
        # 완전히 지어낸 항목 (데이터에 유사 항목조차 없음) -> "없음"으로 잡혀야 함
        {"country": "아랍에미리트", "topic": "12. 패키지 및 단기 투어", "item": "우주여행 체험 프로그램", "value": 77.7},
        # 진짜 존재하는 항목이지만 값을 지어낸 경우 -> "값 불일치"로 잡혀야 함
        {"country": "아랍에미리트", "topic": "12. 패키지 및 단기 투어", "item": "픽업 서비스", "value": 99.9},
    ]
    problems = verify_citations(fake_citations, lookup)
    return {
        "label": "SANITY — 고의로 지어낸 인용 2건 (완전 창작 + 값 조작)",
        "citations": fake_citations,
        "verification_problems": problems,
        "verdict": "PASS (전부 검증됨) - 문제! 걸러지지 않음" if not problems else f"올바르게 차단됨 ({len(problems)}건)",
    }


def main() -> None:
    repo = PostgresDataRepository()
    svc = ChatService(repo)
    client = OpenAI(api_key=LLM_API_KEY)

    results = [run_sanity_check()]
    for case in TEST_CASES:
        parsed = ask_with_citations(svc, client, case["question"])
        citations = parsed.get("citations", [])
        lookup = build_lookup(case["countries_for_lookup"])
        problems = verify_citations(citations, lookup)

        results.append(
            {
                "label": case["label"],
                "question": case["question"],
                "answer": parsed.get("answer"),
                "citations": citations,
                "verification_problems": problems,
                "verdict": "FAIL (미검증 인용 발견)" if problems else "PASS (전부 검증됨)",
            }
        )

    RESULT_FILE.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    for r in results:
        print(f"\n=== {r['label']} ===")
        print(f"verdict: {r['verdict']}")
        print(f"citations: {len(r['citations'])}개, problems: {len(r['verification_problems'])}개")
    print(f"\n전체 결과는 {RESULT_FILE} 에 저장됨")


if __name__ == "__main__":
    main()
