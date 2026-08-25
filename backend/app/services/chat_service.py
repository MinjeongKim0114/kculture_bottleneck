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
from psycopg.rows import dict_row

from app.core.config import DATABASE_URL, LLM_API_KEY, LLM_MODEL
from app.data_access.repository import DataRepository

# reddit_qualitative_evidence.business_theme은 AI가 자유 텍스트로 붙인 라벨이라
# 표현이 제각각이다. data/scripts/build_business_opportunity_report.py와 동일한
# 클러스터 정의를 재사용해서 상시 컨텍스트로 넣을 6개 테마를 묶는다.
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
    - population_type이 아직 사람이 최종 검토하지 않은 AI 1차 판정임을
      인지하고, 단정적으로 서술하지 마세요("~일 수 있다", "~라는 사례가
      있다" 톤 유지).
    - 답변 본문에 Reddit permalink(URL)를 직접 노출하지 마세요. "~라는 사례가
      관찰됩니다" 정도로 서술하고, 링크는 붙이지 않습니다.
    - 이 자료가 질문과 안 맞으면 억지로 쓰지 말고 무시하세요.
    - 특정 국가에 대한 질문에는, 정성적 참고자료가 그 국가 화자의 것이라고
      확인되지 않는 한(nationality 명시) 그 국가 고유의 근거인 것처럼
      단정하지 말고 "일반적으로 관찰되는 사례"로만 참고하세요.
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

    def _fetch_reddit_evidence(self) -> list[dict]:
        with psycopg.connect(DATABASE_URL, row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT population_type, business_theme, business_theme_reason, "
                    "title, permalink FROM reddit_qualitative_evidence "
                    "WHERE population_type != '무관'"
                )
                return cur.fetchall()

    def _build_qualitative_context(self, examples_per_cluster: int = 3) -> str:
        rows = self._fetch_reddit_evidence()
        theme_to_cluster = {
            theme: cluster for cluster, themes in THEME_CLUSTERS.items() for theme in themes
        }
        clustered: dict[str, list[dict]] = {c: [] for c in THEME_CLUSTERS}
        for r in rows:
            cluster = theme_to_cluster.get(r.get("business_theme"))
            if cluster:
                clustered[cluster].append(r)

        lines = [
            "[정성적 참고자료 — Reddit, 규칙 12번 준수해서 사용]",
            "출처: 체류/방문 외국인이 Reddit에 남긴 글(942건 중 population_type이 "
            "'무관'이 아닌 것만). 관계, 대표성, 사용 규칙은 시스템 규칙 12번 참고.",
        ]
        for cluster, cluster_rows in clustered.items():
            if not cluster_rows:
                continue
            pop_counts: dict[str, int] = {}
            for r in cluster_rows:
                pop_counts[r["population_type"]] = pop_counts.get(r["population_type"], 0) + 1
            lines.append(f"\n## {cluster} ({len(cluster_rows)}건, {pop_counts})")
            for r in cluster_rows[:examples_per_cluster]:
                lines.append(
                    f"- [{r['population_type']}] \"{r['title']}\" — "
                    f"{r.get('business_theme_reason', '')} (출처: {r['permalink']})"
                )
        return "\n".join(lines)

    def ask(self, question: str) -> str:
        content = (
            f"[데이터]\n{self._build_context()}\n\n"
            f"{self._build_qualitative_context()}\n\n"
            f"[질문]\n{question}"
        )
        response = self._client.chat.completions.create(
            model=LLM_MODEL,
            temperature=0,
            seed=42,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": content},
            ],
        )
        return response.choices[0].message.content
