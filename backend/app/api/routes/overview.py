from fastapi import APIRouter, Depends

from app.api.deps import get_dashboard_service
from app.services.dashboard_service import DashboardService

router = APIRouter(prefix="/api/overview", tags=["overview"])


@router.get("")
def get_overview(service: DashboardService = Depends(get_dashboard_service)) -> dict:
    """23개국 전체 개요: 지표 분포, 국가 그리드, 병목 유형 요약."""
    return service.get_overview()
