from fastapi import APIRouter, Depends

from app.api.deps import get_dashboard_service
from app.services.dashboard_service import DashboardService

router = APIRouter(prefix="/api/barriers", tags=["barriers"])


@router.get("")
def get_barrier_explorer(service: DashboardService = Depends(get_dashboard_service)) -> dict:
    """Barrier Explorer용: 23개국 x 8개 장벽 heatmap 데이터 + 그룹 매핑."""
    return service.get_barrier_explorer()
