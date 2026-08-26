"""Chatbot service.

Answers are grounded in the A/B-grade quantitative tables defined in
dashboard_data_dictionary.md, plus a small curated summary of Reddit
qualitative evidence (Track 1/2, table 14 in the dictionary) for business-
opportunity framing. The LLM narrates/explains these; it never invents or
recomputes a statistic, and never treats Reddit counts as survey percentages.
"""
import json

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


def _country_search_terms(country: str) -> list[str]:
    for group in COUNTRY_ALIAS_GROUPS:
        if country in group:
            return group
    return [country]


SYSTEM_PROMPT = """당신은 '한류 인지-행동 Gap' 분석 대시보드의 AI Analyst입니다.
사용자 메시지에 포함된 [데이터] JSON에 있는 값만 근거로 답변하세요.

반드시 지켜야 할 규칙:
1. [데이터]에 없는 수치나 국가를 지어내지 마세요. 데이터로 답할 수 없으면
   "현재 데이터로는 답변할 수 없습니다"라고 솔직히 말하세요.
2. 모든 퍼센트 값은 국가 단위 응답 비율이며, 개인 단위 확률이 아닙니다.
3. gap_tier, *_tier, overly_broad_flag 등은 23개국 사이의 상대적 위치이며
   절대적 기준이 아닙니다. "상위/하위 3분위" 같은 표현을 유지하세요.
4. small_sample_flag가 'Y'이거나 barrier_flag가 '가능성(소표본 주의)'인
   경우, 표본이 작다는 주의를 함께 언급하세요. 'Y'로 뭉개지 마세요.
5. gap_analysis(Direct Gap)와 conditional_gap_analysis(Conditional Gap)는
   서로 다른 축입니다. 두 값을 더하거나 같은 지표처럼 섞지 마세요.
6. gap_barrier_correlation/sensitivity_analysis의 r/p 값을 "원인",
   "영향", "효과", "주요 요인"으로 재서술하지 마세요. 반드시 "○○와 ○○
   사이에 [direction] 상관관계가 관찰되었다" 형식으로만 서술하세요.
7. 특정 국가의 장벽/유형을 언급할 때는 그 국가의
   country_bottleneck_profile.key_observed_pattern에 나열된 모든 항목을
   빠짐없이 확인하고 답변에 반영하세요. 그 중 일부만 골라 언급하지
   마세요. (해당 필드는 "Y"로 판정된 유형을 세미콜론으로 구분해 전부
   나열한 것입니다.)
8. 특정 국가의 지표가 23개국 중 어디쯤 위치하는지 말할 때는 반드시
   country_pattern_profile의 해당 `_tier` 필드(하위/중위/상위3분위)를
   그대로 인용하세요. "평균보다 높다/낮다"처럼 직접 숫자를 비교해서
   판단하지 마세요 — 그 비교는 이미 `_tier` 컬럼으로 계산되어
   있으므로, 당신은 계산하지 않고 인용만 합니다. country_pattern_profile에
   해당 국가/지표의 `_tier` 값이 없으면 상대적 위치를 언급하지 말고
   숫자만 제시하세요 (없는 값을 스스로 계산해서 채우지 마세요).
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
    - BASE가 barrier_pattern_analysis(방문 비의향자)와 다릅니다(콘텐츠
      경험/인지자 기준). 두 표의 값을 같은 모집단인 것처럼 직접 비교하거나
      합산하지 마세요.
14. [국가별 관찰 로그](country_bottleneck_observations)가 포함되어 있으면,
    `detail`과 `confidence` 필드를 재요약하지 말고 원문 그대로 인용하세요.
    이건 이미 사람이 다른 표들을 근거로 미리 정리해둔 관찰 문장입니다.
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
16. analysis_long이 포함되어 있으면, 이건 다른 모든 표의 계산 원천
    롱포맷입니다. 이미 인용한 값의 출처(어느 table_id/조사에서 나왔는지)를
    확인하는 용도로만 쓰고, 여기서 새로운 값을 계산하거나 다른 표와 다른
    숫자가 나오면 그 표 값을 우선하세요(가공되지 않은 원천이라 반올림 등의
    차이가 있을 수 있음).
"""


class ChatService:
    def __init__(self, repo: DataRepository):
        self._repo = repo
        self._client = OpenAI(api_key=LLM_API_KEY)

    def _build_context(self) -> str:
        data = {
            "country_profile_base": self._repo.get_country_profiles(),
            "gap_analysis": self._repo.get_gap_analysis(),
            "conditional_gap_analysis": self._repo.get_conditional_gap_analysis(),
            "barrier_pattern_analysis": self._repo.get_barrier_pattern_analysis(),
            "country_bottleneck_profile": self._repo.get_bottleneck_profiles(),
            "bottleneck_type_summary": self._repo.get_bottleneck_type_summary(),
            "gap_barrier_correlation": self._repo.get_gap_barrier_correlation(),
            "sensitivity_analysis": self._repo.get_sensitivity_analysis(),
            "country_indicator_distribution": self._repo.get_country_indicator_distribution(),
            "country_pattern_profile": self._repo.get_country_pattern_profiles(),
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

    def _build_2025_survey_context(self, question: str) -> str:
        with psycopg.connect(DATABASE_URL, row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT DISTINCT segment FROM potential_tourist_2025_survey WHERE \"group\" = '거주국별'"
                )
                known = [r["segment"] for r in cur.fetchall()]
                matched = self._match_country(question, known)
                if not matched:
                    return ""
                # 국가당 최대 826행까지 나올 수 있어 컨텍스트 초과를 유발한 적이 있음
                # (실측: UAE 826행 + analysis_long 246행 → 128k 토큰 한도 초과) - 상한을 둔다.
                cur.execute(
                    "SELECT topic, segment, sample_n, item, value "
                    "FROM potential_tourist_2025_survey "
                    "WHERE \"group\" = '거주국별' AND segment = ANY(%s) "
                    "ORDER BY page LIMIT 300",
                    (matched,),
                )
                rows = cur.fetchall()
        if not rows:
            return ""
        return (
            "[2025 잠재방한여행객조사 — dashboard_data_dictionary.md 15절, 규칙 15번 준수. "
            "국가 총계만 있음, 성별/연령별 세그먼트 없음. 컨텍스트 크기 제한으로 일부 항목만 포함됨]\n"
            f"{json.dumps(rows, ensure_ascii=False)}"
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

    def ask(self, question: str) -> str:
        # analysis_long은 다른 표들의 원천 롱포맷이라 내용이 중복이고, 국가당 최대
        # 수백 행이라 상시 주입하면 컨텍스트 한도를 넘긴다(dashboard_data_dictionary.md
        # 12절 설계 의도대로 "출처 확인용"으로만 남겨두고 기본 주입에서는 제외한다).
        blocks = [
            self._build_content_reasons_context(question),
            self._build_bottleneck_observations_context(question),
            self._build_2025_survey_context(question),
        ]
        extra = "\n\n".join(b for b in blocks if b)
        content = (
            f"[데이터]\n{self._build_context()}\n\n"
            f"{self._build_qualitative_context(question)}\n\n"
            + (f"{extra}\n\n" if extra else "")
            + f"[질문]\n{question}"
        )
        response = self._client.chat.completions.create(
            model=LLM_MODEL,
            seed=42,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": content},
            ],
        )
        return response.choices[0].message.content
