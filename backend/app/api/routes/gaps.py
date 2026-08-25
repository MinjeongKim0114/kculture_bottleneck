from fastapi import APIRouter, Depends

from app.api.deps import get_dashboard_service
from app.services.dashboard_service import DashboardService

router = APIRouter(prefix="/api/gaps", tags=["gaps"])


@router.get("")
def get_gap_explorer(service: DashboardService = Depends(get_dashboard_service)) -> dict:
    """Gap Explorer용: Direct Gap, Conditional Gap을 별개 섹션으로 반환."""
    return service.get_gap_explorer()
