from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_dashboard_service, get_repository
from app.data_access.repository import DataRepository
from app.services.dashboard_service import DashboardService
from app.services.exceptions import CountryNotFoundError

router = APIRouter(prefix="/api/countries", tags=["countries"])


@router.get("")
def list_countries(repo: DataRepository = Depends(get_repository)) -> list[str]:
    """23개국 국가명 목록 (country_profile_base.csv 기준)."""
    return repo.list_countries()


@router.get("/{country}")
def get_country_detail(
    country: str, service: DashboardService = Depends(get_dashboard_service)
) -> dict:
    """Country Explorer용 단일 국가 전체 프로파일."""
    try:
        return service.get_country_detail(country)
    except CountryNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
