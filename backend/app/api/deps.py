"""Shared FastAPI dependencies.

A single CsvDataRepository/DashboardService pair is reused across requests
(CSVs are cached in memory after first read). Swapping to PostgreSQL later
only means constructing a different DataRepository implementation here.
"""
from functools import lru_cache

from app.data_access.csv_repository import CsvDataRepository
from app.data_access.repository import DataRepository
from app.services.dashboard_service import DashboardService


@lru_cache
def get_repository() -> DataRepository:
    return CsvDataRepository()


@lru_cache
def get_dashboard_service() -> DashboardService:
    return DashboardService(get_repository())
