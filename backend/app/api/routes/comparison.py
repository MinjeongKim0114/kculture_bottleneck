from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import get_dashboard_service
from app.services.dashboard_service import DashboardService
from app.services.exceptions import CountryNotFoundError, InvalidComparisonRequestError

router = APIRouter(prefix="/api/comparison", tags=["comparison"])


@router.get("")
def get_comparison(
    countries: list[str] = Query(..., description="비교할 국가 2~3개, 예: ?countries=러시아&countries=일본"),
    service: DashboardService = Depends(get_dashboard_service),
) -> dict:
    """Comparison용: 선택한 2~3개국의 Country Explorer 프로파일을 나란히 반환."""
    try:
        return service.get_comparison(countries)
    except InvalidComparisonRequestError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except CountryNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
