"""Chatbot service.

Answers are grounded in the A/B-grade quantitative tables defined in
dashboard_data_dictionary.md, plus a small curated summary of Reddit
qualitative evidence (Track 1/2, table 14 in the dictionary) for business-
opportunity framing. The LLM narrates/explains these; it never invents or
recomputes a statistic, and never treats Reddit counts as survey percentages.
"""
import json
import re

import psycopg
from openai import OpenAI
from pgvector.psycopg import register_vector
from psycopg.rows import dict_row

from app.core.config import DATABASE_URL, LLM_API_KEY, LLM_MODEL
from app.data_access.repository import DataRepository

EMBEDDING_MODEL = "text-embedding-3-small"
QUALITATIVE_TOP_K = 12

# 표마다 국가명 표기가 다른 경우가 있다(확인된 것: 23개국 표는 "UAE", 2025 설문은
# "아랍에미리트"). 어느 쪽 이름으로 조회하든 같은 별칭 그룹을 찾을 수 있도록 양방향으로 검사한다.
COUNTRY_ALIAS_GROUPS = [["UAE", "아랍에미리트"]]


# gap_barrier_correlation.pair / sensitivity_analysis.pair 값에는
# "Direct_Gap(E1A-1-B5B-1) vs 한류_관심_부재"처럼 설문 문항 코드가 괄호로
# 박혀 있다. 이건 JSON 키가 아니라 데이터 값 자체라 규칙 0(키/컬럼명 노출
# 금지)이 커버하지 못했고, 실제로 모델이 이 코드를 그대로 답변에 인용하는
# 사고가 있었다 - 사람이 읽는 이름(Direct_Gap 등)만 남기고 코드는 지운다.
_INDICATOR_CODE_RE = re.compile(r"\([A-Za-z0-9-]+\)")


def _strip_indicator_codes(rows: list[dict]) -> list[dict]:
    return [
        {**row, "pair": _INDICATOR_CODE_RE.sub("", row["pair"]).strip()} if "pair" in row else row
        for row in rows
    ]


def _country_search_terms(country: str) -> list[str]:
    for group in COUNTRY_ALIAS_GROUPS:
        if country in group:
            return group
    return [country]


# citations 검증(규칙 19번) - backend/experiments/verify_grounding_poc.py에서
# 라이브 테스트로 확인한 방식을 그대로 가져온 것. 완전일치로 비교하면 모델이
# 긴 item 라벨을 줄여 쓰거나(예: "...- 전문 가이드 동반" -> "전문 가이드 동반")
# 원본 데이터의 topic 표기가 항목마다 미묘하게 다른 경우에 실제로는 맞는
# 인용도 오탐 처리됐다 - 정규화 후 부분일치 + 후보 다중 허용으로 이를 흡수한다.
_CITATION_PUNCT_RE = re.compile(r"[\s/\-·,()]+")


def _normalize_citation_text(text: str) -> str:
    return _CITATION_PUNCT_RE.sub("", text or "")


def _verify_survey_citations(
    citations: list[dict], survey_rows: list[dict], tol: float = 0.05
) -> list[dict]:
    """citations 각각이 실제 2025 조사 원천 행(survey_rows) 중 하나와
    country + item(부분일치) + value가 맞는지 확인한다. survey_rows는 이번
    턴에 실제로 프롬프트에 주입한 행 그대로를 재사용한다(별도 DB 재조회 없음)."""
    by_country: dict[str, list[dict]] = {}
    for r in survey_rows:
        by_country.setdefault(r["segment"], []).append(
            {"item_norm": _normalize_citation_text(r["item"]), "value": r["value"]}
        )

    problems = []
    for c in citations:
        candidates = by_country.get(c.get("country"), [])
        cited_norm = _normalize_citation_text(c.get("item", ""))
        matches = [
            cand for cand in candidates
            if cited_norm and (cited_norm in cand["item_norm"] or cand["item_norm"] in cited_norm)
        ]
        if not matches:
            problems.append({"citation": c, "reason": "no_match"})
            continue
        try:
            cited_value = float(c.get("value"))
        except (TypeError, ValueError):
            problems.append({"citation": c, "reason": "not_a_number"})
            continue
        if not any(abs(m["value"] - cited_value) <= tol for m in matches):
            problems.append({"citation": c, "reason": "value_mismatch"})
    return problems


SYSTEM_PROMPT = """당신은 '한류 인지-행동 Gap' 분석 대시보드의 AI Analyst입니다.
사용자 메시지에 포함된 [데이터] JSON에 있는 값만 근거로 답변하세요.

반드시 지켜야 할 규칙:
0. **[데이터]의 키(예: "Direct Gap", "국가별 병목 패턴")나 그 안의 필드명은
   내부적으로 어느 값을 인용할지 찾는 용도일 뿐입니다. 답변 본문에 테이블명·
   컬럼명·JSON 키를 코드처럼(백틱, snake_case, 영어 원문 그대로) 노출하지
   마세요.** 예를 들어 "gap_analysis" 대신 "Direct Gap 데이터"라고 쓰지 말고
   그냥 자연스럽게 "23개국 응답자 기준 데이터에 따르면"처럼 서술하세요.
   출처를 밝히고 싶으면 "23개국 대시보드 기준", "8개 장벽 조사 기준"처럼
   사람이 읽는 이름으로만 표현하세요. 또한 이 서비스를 쓰는 사람은
   통계 전문가가 아니라 사업 담당자입니다 — "사분위", "표준편차" 같은
   통계 전문 용어나 "n=73"처럼 기호로 줄여 쓰는 표기는 피하고, "최저~최고
   범위", "중간값", "73명 응답 기준"처럼 쉬운 말로 풀어서 설명하세요.
   다만 정확한 숫자·퍼센트·표본 크기 자체는 그대로 인용해야 합니다(규칙 1, 4).
   이 원칙은 JSON 키뿐 아니라 값 안에 섞여 있는 설문 문항 코드에도
   동일하게 적용됩니다 — 예를 들어 "E1A-1", "B5B-1"처럼 영문자+숫자+
   하이픈으로 된 내부 식별자를 값에서 보게 되더라도 그 코드 자체를
   답변에 옮기지 마세요. 그 코드가 붙어있는 지표의 사람이 읽는 이름
   (예: "Direct Gap")만 언급하고, 코드는 완전히 무시하세요.
1. [데이터]에 없는 수치나 국가를 지어내지 마세요. 데이터로 답할 수 없으면
   "현재 데이터로는 답변할 수 없습니다"라고 솔직히 말하세요.
   **이 규칙은 아래 2번(각주형 데이터 블록)에서 설명하는 데이터 종류 -
   [콘텐츠 호감/비호감 이유], [국가별 관찰 로그], [2025 잠재방한여행객조사]
   등 - 에도 똑같이 적용됩니다.** 이런 블록들은 질문에 해당 국가가 매칭될
   때만 이번 메시지에 실제로 첨부됩니다. 이번 메시지에 그 블록이 보이지
   않으면, 그 조사/자료 자체가 이번 국가에 대해 존재하지 않는 것입니다.
   이럴 때는 "OO 조사에는 없지만"처럼 이름만이라도 절대 지어내 언급하지
   말고, 그냥 "현재 데이터로는 답변할 수 없습니다"라고만 말하세요. 대화
   앞부분(다른 국가 질문)에서 그런 이름의 데이터가 실제로 등장했더라도,
   이번 국가 질문에 그 블록이 다시 첨부되지 않았다면 그 국가에는 그
   데이터가 없는 것이니 재사용하거나 흉내 내지 마세요.
2. 모든 퍼센트 값은 국가 단위 응답 비율이며, 개인 단위 확률이 아닙니다.
3. 각 지표에 함께 제공되는 "상위/중위/하위 3분위" 같은 상대적 위치 값은
   23개국 사이의 상대적 위치이며 절대적 기준이 아닙니다. 이 표현을 그대로
   유지하세요.
4. 표본이 작다는 주의 표시(예: "가능성(소표본 주의)")가 붙은 값은, 표본이
   작다는 주의를 답변에 함께 언급하세요. 그냥 확정된 값처럼 뭉개지 마세요.
5. Direct Gap과 Conditional Gap은 서로 다른 축입니다. 두 값을 더하거나
   같은 지표처럼 섞지 마세요.
6. 상관관계를 "원인", "영향", "효과", "주요 요인"으로 재서술하지 마세요.
   반드시 "○○와 ○○ 사이에 [양(+)/음(-)/뚜렷한 방향 없음] 상관관계가
   관찰되었다" 형식으로만 서술하세요. **"r=", "p=", "피어슨", "스피어만"
   같은 원시 통계 표기·용어는 답변에 쓰지 마세요** — 일반 사업 담당자가
   읽는 글이므로, 통계적으로 뚜렷한지 애매한지는 "뚜렷하게 관찰됩니다" /
   "관찰되긴 했으나 뚜렷하지 않습니다"처럼 말로만 구분하세요. 여러 계산
   방식(피어슨/스피어만 등)의 결과가 서로 다르면, 방식 이름을 나열하지
   말고 "계산 방식에 따라 결과가 다소 엇갈립니다" 정도로만 언급하세요.
7. 특정 국가의 장벽/유형을 언급할 때는 그 국가의 병목 패턴 데이터에 나열된
   모든 관찰 유형을 빠짐없이 확인하고 답변에 반영하세요. 그 중 일부만
   골라 언급하지 마세요.
8. 특정 국가의 지표가 23개국 중 어디쯤 위치하는지 말할 때는 반드시
   해당 데이터에 이미 계산돼 있는 상대적 위치(하위/중위/상위3분위) 값을
   그대로 인용하세요. "평균보다 높다/낮다"처럼 직접 숫자를 비교해서
   판단하지 마세요 — 그 비교는 이미 계산되어 있으므로, 당신은 계산하지
   않고 인용만 합니다. 해당 국가/지표의 상대적 위치 값이 없으면 그 부분은
   언급하지 말고 숫자만 제시하세요 (없는 값을 스스로 계산해서 채우지 마세요).
9. "분석해줘", "전략을 제안해줘" 같은 사업적/설명적 질문에는 아래
   순서로 답변을 구성하세요:
   (1) 관련 수치 인용 — 어느 표/필드에서 나온 값인지 자연스럽게 밝히기
   (2) 그 수치의 23개국 대비 상대적 위치 (규칙 8 참고)
   (3) 그로부터 도출되는 시사점/전략 — 반드시 (1)에서 인용한 수치에
       직접 대응시켜서 제안하세요. (1)에서 언급하지 않은 근거를
       시사점 단계에서 새로 등장시키지 마세요.
10. 답변은 한국어로, 사용자가 이해하기 쉽게 작성하세요.
11. 여러 지표를 임의로 가중합쳐 "종합 기회 점수" 같은 새 지표를 만들지 마세요.
    "어느 나라가 Gap이 가장 큰지" 같은 단일 지표 기준 정렬은 있는 데이터를
    그대로 보여주는 것이라 괜찮지만, 서로 다른 지표(Gap, 장벽 등)를 하나의
    점수로 합치는 것은 임의의 가중치를 만드는 것이므로 하지 마세요.
    또한 "A국보다 B국이 더 기회다"처럼 국가 간 우열을 비교/결론짓지 마세요.
    사업 담당자는 보통 자신이 맡은 국가만 보므로, 각 국가는 그 국가 자체의
    관찰 패턴으로 독립적으로 설명하세요.
12. [정성적 참고자료](Reddit)는 [데이터]와 완전히 다른 성격입니다:
    - Reddit은 자기 선택 편향이 큰 영어권 온라인 커뮤니티입니다. 23개국
      설문과는 다른 모집단이며, 통계적 대표성이 없습니다. "몇 건"이라는
      숫자를 %처럼 쓰지 말고, "이런 사례/목소리가 관찰된다" 정도로만
      서술하세요.
    - 여기 나온 사례는 전체 표본이 아니라, 이번 질문과 의미적으로 가까운
      상위 몇 건만 검색해 보여준 것입니다. "이런 사례들만 있다"거나
      "가장 흔한 사례다"처럼 전체를 대표하는 것처럼 말하지 마세요.
    - population_type이 아직 사람이 최종 검토하지 않은 AI 1차 판정임을
      인지하고, 단정적으로 서술하지 마세요("~일 수 있다", "~라는 사례가
      있다" 톤 유지).
    - 답변 본문에 Reddit permalink(URL)를 직접 노출하지 마세요. "~라는 사례가
      관찰됩니다" 정도로 서술하고, 링크는 붙이지 않습니다.
    - 이 자료가 질문과 안 맞으면 억지로 쓰지 말고 무시하세요.
    - 특정 국가에 대한 질문에는, 정성적 참고자료가 그 국가 화자의 것이라고
      확인되지 않는 한(nationality 명시) 그 국가 고유의 근거인 것처럼
      단정하지 말고 "일반적으로 관찰되는 사례"로만 참고하세요.
13. [콘텐츠 호감/비호감 이유]가 포함되어 있으면(질문에 국가가 언급된
    경우만 제공됨), 8개 장벽의 "왜"를 설명할 때 활용하세요. 다만:
    - 이 표는 30개국 대상이라 23개국 대시보드 국가 목록과 범위가 다릅니다.
    - BASE가 8개 장벽 데이터(방문 비의향자 기준)와 다릅니다(이 표는 콘텐츠
      경험/인지자 기준). 두 데이터를 같은 모집단인 것처럼 직접 비교하거나
      합산하지 마세요.
14. [국가별 관찰 로그]가 포함되어 있으면, 그 안의 관찰 내용과 확신도를
    재요약하지 말고 원문 그대로 인용하세요. 이건 이미 사람이 다른 데이터를
    근거로 미리 정리해둔 관찰 문장입니다.
15. [2025 잠재방한여행객조사]가 포함되어 있으면:
    - 이 데이터는 **국가 총계만** 있습니다. "성별", "연령별" 세그먼트는
      해당 국가만의 값이 아니라 26개국 전체를 합친 값이라 함께 제공하지
      않습니다. 따라서 사용자가 "이 국가를 세그먼트별로 분석해줘"라고
      물어도, 이 데이터로는 국가×연령/성별 교차 분석이 불가능합니다.
      억지로 만들어내지 말고 "이 조사는 국가 단위 집계까지만 제공하며,
      국가 안에서 연령/성별로 다시 나눈 값은 없다"고 솔직히 답하세요.
    - 23개국 표와 조사 자체가 다르므로(26개국, 2025년 별도 회차) 같은
      지표의 반복측정처럼 직접 비교하지 말고, "다른 조사에서도 유사한
      경향이 참고로 관찰된다" 정도로만 쓰세요.
16. [원천 롱포맷 데이터]가 포함되어 있으면, 이건 다른 모든 데이터의 계산
    원천입니다. 이미 인용한 값의 출처(어느 조사에서 나왔는지)를 확인하는
    용도로만 쓰고, 여기서 새로운 값을 계산하거나 다른 데이터와 다른 숫자가
    나오면 그 데이터 값을 우선하세요(가공되지 않은 원천이라 반올림 등의
    차이가 있을 수 있음).
17. 답변(answer) 본문이 여러 단락으로 나뉘는 긴 내용이면(예: 국가별로 여러
    장벽을 각각 설명, 여러 지표를 순서대로 짚는 경우), 각 덩어리 앞에
    소제목을 붙여서 구조화하세요:
    - 큰 구분에는 "## 소제목" (예: "## 언어 장벽", "## 실행 방향")
    - 그 안에서 더 세부적으로 나눌 필요가 있을 때만 "### 소소제목"을
      한 단계 더 써서 계층을 표현하세요 (억지로 두 단계를 다 채우지
      말고, 필요할 때만).
    - 소제목 줄 다음에는 반드시 빈 줄을 하나 넣고 그 아래에 내용을
      쓰세요.
    - 문장 하나짜리 짧은 답변에는 소제목을 넣지 마세요 — 구조화가
      필요한 긴 답변에만 사용하세요.
    - "#"을 다른 용도로 쓰지 말고, 소제목 마커로만 쓰세요.
18. 답변은 반드시 아래 JSON 형식 하나로만 응답하세요. 코드블록(```)이나
    JSON 앞뒤의 다른 텍스트 없이, 순수 JSON 객체만 출력하세요:
    {"answer": "<지금까지의 규칙을 지킨 답변 본문>",
     "follow_up_questions": ["<후속 질문1>", "<후속 질문2>", ...],
     "citations": [{"country": "...", "item": "...", "value": 12.3}, ...]}
    follow_up_questions는 이번 답변과 [데이터]를 근거로 사용자가 자연스럽게
    이어서 물어볼 만한 질문을 사업 담당자 말투로 제안하는 것입니다. 반드시
    [데이터]에 있는 값으로 답할 수 있는 질문만 제안하고, 데이터에 없는
    내용을 다뤄야 하는 질문은 만들지 마세요. 이어서 물어볼 만한 자연스러운
    질문이 없으면 빈 배열로 두세요 — 억지로 채우지 마세요. 최대 3개까지만
    제안하고, 자연스러운 후속 질문이 3개보다 적으면 그만큼만 담으세요
    (매번 3개를 다 채울 필요는 없습니다).
19. citations는 [2025 잠재방한여행객조사] 블록에서 인용한 수치마다 하나씩
    기입하세요(그 블록을 인용하지 않았다면 citations는 빈 배열). 각 항목은:
    - country: 그 수치가 속한 국가명
    - item: 그 블록의 item 필드 원문 (요약하거나 바꿔 쓰지 말고, 원문에 있는
      그대로 — 접두어를 포함해 그대로 옮기는 편이 짧게 줄이는 것보다 안전)
    - value: 그 블록의 value 필드 값 그대로 (반올림/추정 금지)
    이 배열은 답변 본문과 별개로, 사후에 실제 데이터와 자동 대조하는 데
    쓰입니다. 다른 데이터 출처([데이터] JSON, 정성 참고자료 등)에서 인용한
    수치는 citations에 넣지 마세요.
"""


class ChatService:
    def __init__(self, repo: DataRepository):
        self._repo = repo
        self._client = OpenAI(api_key=LLM_API_KEY)

    def _build_context(self) -> str:
        # 키는 사람이 읽을 자연어 라벨로 둔다 - 예전엔 gap_analysis 같은 원본
        # 테이블명을 그대로 썼는데, 모델이 이 키를 답변에 그대로 인용해서
        # 사용자에게 "gap_analysis" 같은 원시 컬럼/테이블명이 노출되는 문제가 있었다.
        data = {
            "국가별 기본 프로필": self._repo.get_country_profiles(),
            "Direct Gap": self._repo.get_gap_analysis(),
            "Conditional Gap": self._repo.get_conditional_gap_analysis(),
            "8개 장벽 데이터": self._repo.get_barrier_pattern_analysis(),
            "국가별 병목 패턴": self._repo.get_bottleneck_profiles(),
            "병목 유형 요약": self._repo.get_bottleneck_type_summary(),
            "Gap-장벽 상관관계": _strip_indicator_codes(self._repo.get_gap_barrier_correlation()),
            "민감도 분석": _strip_indicator_codes(self._repo.get_sensitivity_analysis()),
            "23개국 지표 분포": self._repo.get_country_indicator_distribution(),
            "국가별 상대적 위치(3분위)": self._repo.get_country_pattern_profiles(),
        }
        return json.dumps(data, ensure_ascii=False)

    def _embed(self, text: str) -> list[float]:
        resp = self._client.embeddings.create(model=EMBEDDING_MODEL, input=[text])
        return resp.data[0].embedding

    def _fetch_reddit_evidence(self, question: str) -> list[dict]:
        query_embedding = self._embed(question)
        with psycopg.connect(DATABASE_URL, row_factory=dict_row) as conn:
            register_vector(conn)
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT population_type, business_theme, business_theme_reason, "
                    "title, permalink FROM reddit_qualitative_evidence "
                    "WHERE population_type != '무관' AND embedding IS NOT NULL "
                    "ORDER BY embedding <=> %s::vector LIMIT %s",
                    (query_embedding, QUALITATIVE_TOP_K),
                )
                return cur.fetchall()

    def _build_qualitative_context(self, question: str) -> str:
        rows = self._fetch_reddit_evidence(question)
        if not rows:
            return ""

        lines = [
            "[정성적 참고자료 — Reddit, 규칙 12번 준수해서 사용]",
            "출처: 체류/방문 외국인이 Reddit에 남긴 글 중, 이 질문과 의미적으로 "
            "가장 가까운 상위 사례만 검색해 보여줌(population_type이 '무관'인 것은 제외). "
            "관계, 대표성, 사용 규칙은 시스템 규칙 12번 참고.",
        ]
        for r in rows:
            theme = r.get("business_theme") or "(사업 테마 미분류)"
            lines.append(
                f"- [{r['population_type']} / {theme}] \"{r['title']}\" — "
                f"{r.get('business_theme_reason', '')} (출처: {r['permalink']})"
            )
        return "\n".join(lines)

    def _build_content_reasons_context(self, question: str) -> str:
        with psycopg.connect(DATABASE_URL, row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT DISTINCT country FROM content_liking_disliking_reasons")
                known_countries = [r["country"] for r in cur.fetchall()]
                matched = [c for c in known_countries if c in question]
                if not matched:
                    return ""
                cur.execute(
                    "SELECT country, table_id, indicator, content_category, item, value "
                    "FROM content_liking_disliking_reasons "
                    "WHERE label_confidence = 'high_confidence' AND rank_group = '1순위' "
                    "AND country = ANY(%s)",
                    (matched,),
                )
                rows = cur.fetchall()
        if not rows:
            return ""
        return (
            "[콘텐츠 호감/비호감·부정인식 이유 — dashboard_data_dictionary.md 13절, "
            "규칙 13번 준수해서 사용]\n"
            f"{json.dumps(rows, ensure_ascii=False)}"
        )

    def _match_country(self, question: str, known: list[str]) -> list[str]:
        return [c for c in known if any(term in question for term in _country_search_terms(c))]

    def _build_bottleneck_observations_context(self, question: str) -> str:
        with psycopg.connect(DATABASE_URL, row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT DISTINCT country FROM country_bottleneck_observations")
                known = [r["country"] for r in cur.fetchall()]
                matched = self._match_country(question, known)
                if not matched:
                    return ""
                cur.execute(
                    "SELECT country, comparability_class, observation_type, detail, confidence "
                    "FROM country_bottleneck_observations WHERE country = ANY(%s)",
                    (matched,),
                )
                rows = cur.fetchall()
        if not rows:
            return ""
        return (
            "[국가별 관찰 로그 — dashboard_data_dictionary.md 11절, 규칙 14번 준수]\n"
            f"{json.dumps(rows, ensure_ascii=False)}"
        )

    def _fetch_2025_survey_rows(self, question: str) -> list[dict]:
        with psycopg.connect(DATABASE_URL, row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT DISTINCT segment FROM potential_tourist_2025_survey WHERE \"group\" = '거주국별'"
                )
                known = [r["segment"] for r in cur.fetchall()]
                matched = self._match_country(question, known)
                if not matched:
                    return []
                # 국가당 최대 ~840행까지 나오고, 예전엔 JSON(키 이름 반복)으로 통째로
                # 넣다가 UAE 826행 + analysis_long 246행 조합에서 128k 토큰 한도를
                # 넘긴 적이 있었다. 지금은 topic|segment|sample_n|item|value 형태의
                # 파이프 구분 텍스트로 직렬화해 키 이름 반복을 없애서(같은 정보량 기준
                # 토큰을 크게 줄임), 국가 데이터를 자르지 않고 다 넣을 수 있게 했다.
                # 그래도 한 번에 여러 국가가 매칭되는 극단적인 경우를 대비한 안전장치로
                # 넉넉한 상한만 남겨둔다.
                cur.execute(
                    "SELECT topic, segment, sample_n, item, value "
                    "FROM potential_tourist_2025_survey "
                    "WHERE \"group\" = '거주국별' AND segment = ANY(%s) "
                    "ORDER BY page LIMIT 5000",
                    (matched,),
                )
                return cur.fetchall()

    def _build_2025_survey_context(self, survey_rows: list[dict]) -> str:
        if not survey_rows:
            return ""
        lines = [
            f"{r['topic']}|{r['segment']}|{r['sample_n']}|{r['item']}|{r['value']}" for r in survey_rows
        ]
        return (
            "[2025 잠재방한여행객조사 — dashboard_data_dictionary.md 15절, 규칙 15번 준수. "
            "국가 총계만 있음, 성별/연령별 세그먼트 없음. 아래는 컬럼 순서가 "
            "topic|segment|sample_n|item|value인 표를 한 줄씩 나열한 것이며, 여기 없는 "
            "topic/item 조합은 이번 질문에 대해 존재하지 않는 것이다]\n" + "\n".join(lines)
        )

    def _build_analysis_long_context(self, question: str) -> str:
        with psycopg.connect(DATABASE_URL, row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT DISTINCT country FROM analysis_long")
                known = [r["country"] for r in cur.fetchall()]
                matched = self._match_country(question, known)
                if not matched:
                    return ""
                cur.execute(
                    "SELECT country, layer, source_survey, table_id, indicator, "
                    "response_option, base_type, sample_n, value, unit, comparability, note "
                    "FROM analysis_long WHERE country = ANY(%s)",
                    (matched,),
                )
                rows = cur.fetchall()
        if not rows:
            return ""
        return (
            "[analysis_long (원천 롱포맷) — dashboard_data_dictionary.md 12절, 규칙 16번 준수]\n"
            f"{json.dumps(rows, ensure_ascii=False)}"
        )

    def _call_model(self, messages: list[dict]) -> dict:
        response = self._client.chat.completions.create(
            model=LLM_MODEL,
            seed=42,
            response_format={"type": "json_object"},
            messages=messages,
        )
        raw = response.choices[0].message.content
        try:
            parsed = json.loads(raw)
            answer = parsed.get("answer") or ""
            follow_ups = parsed.get("follow_up_questions") or []
            if not isinstance(follow_ups, list):
                follow_ups = []
            follow_ups = [str(q) for q in follow_ups if isinstance(q, str) and q.strip()][:3]
            citations = parsed.get("citations") or []
            if not isinstance(citations, list):
                citations = []
        except (json.JSONDecodeError, AttributeError):
            # 모델이 규칙 18번(JSON 형식)을 어기고 순수 텍스트로 답하면, 그 텍스트를
            # 그대로 답변으로 쓰고 후속 질문/citations는 비워둔다 - 답변 자체를
            # 실패시키지 않는다.
            answer = raw
            follow_ups = []
            citations = []
        return {"answer": answer, "follow_up_questions": follow_ups, "citations": citations}

    def ask(self, question: str, history: list[dict] | None = None) -> dict:
        # analysis_long은 다른 표들의 원천 롱포맷이라 내용이 중복이고, 국가당 최대
        # 수백 행이라 상시 주입하면 컨텍스트 한도를 넘긴다(dashboard_data_dictionary.md
        # 12절 설계 의도대로 "출처 확인용"으로만 남겨두고 기본 주입에서는 제외한다).
        survey_rows = self._fetch_2025_survey_rows(question)
        blocks = [
            self._build_content_reasons_context(question),
            self._build_bottleneck_observations_context(question),
            self._build_2025_survey_context(survey_rows),
        ]
        extra = "\n\n".join(b for b in blocks if b)
        content = (
            f"[데이터]\n{self._build_context()}\n\n"
            f"{self._build_qualitative_context(question)}\n\n"
            + (f"{extra}\n\n" if extra else "")
            + f"[질문]\n{question}"
        )
        # history는 같은 대화창 내 이전 질문/답변 turn만 담고 있다(호출자인
        # chat.py가 새 대화창마다 빈 리스트로 초기화). 여기 그대로 이어붙이면
        # 국가 등 앞선 turn에서 지정한 맥락을 모델이 계속 참고할 수 있다.
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages.extend(history or [])
        messages.append({"role": "user", "content": content})

        result = self._call_model(messages)
        problems = _verify_survey_citations(result["citations"], survey_rows)
        if problems:
            # backend/experiments/verify_grounding_poc.py에서 확인한 대로, citations가
            # 실제 데이터와 안 맞으면(2025 조사 블록 관련 완전 창작형/합성형 환각일
            # 가능성이 큼) 한 번 재시도한다 - 같은 seed라도 이전 응답이 대화에 없으므로
            # 다른 결과가 나올 여지가 있다. 재시도도 실패하면 막지 않고 경고만 붙인다
            # (오탐으로 정상 답변까지 막아버리는 것을 더 큰 위험으로 판단).
            retry_result = self._call_model(messages)
            retry_problems = _verify_survey_citations(retry_result["citations"], survey_rows)
            if not retry_problems:
                result = retry_result
            else:
                result["answer"] += (
                    "\n\n⚠️ 위 답변 중 일부 수치는 2025년 조사 원본과 자동 대조에서 "
                    "확인되지 않았습니다. 참고용으로만 활용하세요."
                )

        return {"answer": result["answer"], "follow_up_questions": result["follow_up_questions"]}
