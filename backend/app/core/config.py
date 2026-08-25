"""Paths and constants shared across the data-access and API layers.

`dashboard_data_dictionary.md` is the single source of truth for which CSV
files and columns exist. This module only points at their location; it does
not redefine or duplicate the schema.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

# backend/app/core/config.py -> parents[3] == repo root
REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_PROCESSED_DIR = REPO_ROOT / "data" / "processed"
BACKEND_DIR = REPO_ROOT / "backend"

load_dotenv(BACKEND_DIR / ".env")

DATABASE_URL = os.environ.get("DATABASE_URL")
LLM_API_KEY = os.environ.get("LLM_API_KEY")
LLM_MODEL = os.environ.get("LLM_MODEL", "gpt-4o")


class CsvFiles:
    """Filenames as listed in dashboard_data_dictionary.md (A/B grade only)."""

    COUNTRY_PROFILE_BASE = "country_profile_base.csv"
    GAP_ANALYSIS = "gap_analysis.csv"
    CONDITIONAL_GAP_ANALYSIS = "conditional_gap_analysis.csv"
    BARRIER_PATTERN_ANALYSIS = "barrier_pattern_analysis.csv"
    COUNTRY_BOTTLENECK_PROFILE = "country_bottleneck_profile.csv"
    BOTTLENECK_TYPE_SUMMARY = "bottleneck_type_summary.csv"
    GAP_BARRIER_CORRELATION = "gap_barrier_correlation.csv"
    SENSITIVITY_ANALYSIS = "sensitivity_analysis.csv"
    COUNTRY_INDICATOR_DISTRIBUTION = "country_indicator_distribution.csv"
    COUNTRY_PATTERN_PROFILE = "country_pattern_profile.csv"


# 장벽 그룹 매핑은 dashboard_data_dictionary.md 4절에 명시된 원문 그대로다.
# 화면 필터용 구조 정보일 뿐, 새 지표를 계산하지 않는다.
BARRIER_GROUPS = {
    "인지/관심": ["한류_관심_부재", "낮은_한국_인지도"],
    "이미지": ["부정적_한국_이미지"],
    "경제/물리적 접근성": ["여행경비_물가", "장거리_비행"],
    "제도/언어": ["비자_출입국_절차", "불편한_언어소통"],
    "종교/문화환경": ["불편한_종교환경"],
}

# barrier_pattern_analysis.csv의 8개 장벽 컬럼(원문 그대로). Top3 선정 등
# 정렬/선택에만 쓰고 값 자체를 재계산하지 않는다.
BARRIER_COLUMNS = [
    "한류_관심_부재",
    "낮은_한국_인지도",
    "부정적_한국_이미지",
    "불편한_언어소통",
    "여행경비_물가",
    "비자_출입국_절차",
    "장거리_비행",
    "불편한_종교환경",
]
