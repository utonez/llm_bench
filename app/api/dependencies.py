"""FastAPI dependencies. Built once per process; tests replace them via dependency_overrides."""

from functools import lru_cache
from typing import Annotated

from fastapi import Depends

from app.api.service import StatsService
from app.config import Settings
from app.storage.base import ResultRepository
from app.storage.factory import build_repository


@lru_cache
def get_settings() -> Settings:
    return Settings()


@lru_cache
def get_repository() -> ResultRepository:
    return build_repository(get_settings())


@lru_cache
def get_stats_service() -> StatsService:
    settings = get_settings()
    return StatsService(get_repository(), cache_ttl_s=settings.api_cache_ttl_s)


StatsServiceDep = Annotated[StatsService, Depends(get_stats_service)]
