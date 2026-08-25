"""Shared FastAPI dependencies.

A single DataRepository/DashboardService pair is reused across requests.
"""
from functools import lru_cache

from app.data_access.postgres_repository import PostgresDataRepository
from app.data_access.repository import DataRepository
from app.services.chat_service import ChatService
from app.services.dashboard_service import DashboardService


@lru_cache
def get_repository() -> DataRepository:
    return PostgresDataRepository()


@lru_cache
def get_dashboard_service() -> DashboardService:
    return DashboardService(get_repository())


@lru_cache
def get_chat_service() -> ChatService:
    return ChatService(get_repository())
