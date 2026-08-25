"""Chatbot service.

Answers are grounded only in the A/B-grade quantitative tables already
defined in dashboard_data_dictionary.md (the same data the dashboard API
serves). No RAG / qualitative sources yet — those come in a later step.
The LLM is only allowed to narrate/explain these numbers, never invent or
recompute a statistic that isn't already in the data.
"""
import json

from openai import OpenAI

from app.core.config import LLM_API_KEY, LLM_MODEL
from app.data_access.repository import DataRepository

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

    def ask(self, question: str) -> str:
        response = self._client.chat.completions.create(
            model=LLM_MODEL,
            temperature=0,
            seed=42,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"[데이터]\n{self._build_context()}\n\n[질문]\n{question}",
                },
            ],
        )
        return response.choices[0].message.content
