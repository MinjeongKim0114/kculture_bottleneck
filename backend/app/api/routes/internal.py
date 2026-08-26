"""n8n(또는 다른 외부 스케줄러)이 호출하는 내부 전용 엔드포인트.

Reddit 정성 데이터 수집→분류→적재→임베딩 파이프라인은 Python 스크립트라, Docker의
hardened n8n 이미지(패키지 매니저조차 없음) 안에서는 직접 실행할 수 없다. 대신
FastAPI가 서브프로세스로 실행하고 결과 요약만 n8n에 HTTP로 돌려준다(AGENTS.md:
"n8n은 수집/ETL 자동화, 핵심 로직은 FastAPI"). 외부에서 함부로 못 부르도록 공유
비밀 토큰(X-Internal-Token)으로 게이트한다.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

from fastapi import APIRouter, Header, HTTPException

from app.core.config import INTERNAL_PIPELINE_TOKEN

router = APIRouter(prefix="/internal", tags=["internal"])

REPO_ROOT = Path(__file__).resolve().parents[4]
SCRIPTS_DIR = REPO_ROOT / "data" / "scripts"
RUN_SUMMARY_JSON = REPO_ROOT / "data" / "processed" / "qualitative" / "_last_prefilter_run.json"

# 순서 중요: 수집 -> 전처리(신규만 추림+애매 판정) -> 사업테마 분류(신규만) ->
# Supabase 적재(upsert) -> 임베딩 생성(embedding NULL인 것만).
PIPELINE_SCRIPTS = [
    "collect_reddit_qualitative.py",
    "prefilter_reddit_candidates.py",
    "classify_business_opportunity_themes.py",
    "load_track_data_to_supabase.py",
    "generate_reddit_embeddings.py",
]

STEP_TIMEOUT_SEC = 1800


def _check_token(x_internal_token: str | None) -> None:
    if not INTERNAL_PIPELINE_TOKEN:
        raise HTTPException(500, "INTERNAL_PIPELINE_TOKEN이 backend/.env에 설정되지 않았습니다")
    if x_internal_token != INTERNAL_PIPELINE_TOKEN:
        raise HTTPException(403, "invalid token")


@router.post("/reddit-pipeline")
def run_reddit_pipeline(x_internal_token: str | None = Header(default=None)) -> dict:
    _check_token(x_internal_token)

    logs: dict[str, dict] = {}
    for script in PIPELINE_SCRIPTS:
        # Windows에서 자식 프로세스 stdout이 파이프로 연결되면 콘솔이 아니므로
        # 기본 로케일 코드페이지(cp949)로 인코딩됨 - PYTHONIOENCODING을 강제해서
        # UTF-8로 통일한다. 안 하면 로그의 한글이 깨져서 나온다(실제 동작엔 무해).
        result = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / script)],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=STEP_TIMEOUT_SEC,
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        )
        logs[script] = {
            "returncode": result.returncode,
            "stdout_tail": (result.stdout or "")[-3000:],
            "stderr_tail": (result.stderr or "")[-1500:],
        }
        if result.returncode != 0:
            return {
                "status": "failed",
                "failed_step": script,
                "logs": logs,
                "new_total": 0,
                "ambiguous_count": 0,
                "ambiguous": [],
            }

    summary = {"new_total": 0, "ambiguous_count": 0, "ambiguous": []}
    if RUN_SUMMARY_JSON.exists():
        raw = json.loads(RUN_SUMMARY_JSON.read_text(encoding="utf-8"))
        summary = {
            "new_total": raw.get("new_total", 0),
            "ambiguous_count": raw.get("ambiguous_count", 0),
            "ambiguous": raw.get("ambiguous", []),
        }

    return {"status": "ok", "logs": logs, **summary}
