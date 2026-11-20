"""Runtime settings, read from environment variables (and .env locally)."""

from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    storage_backend: Literal["memory", "firestore"] = "memory"
    gcp_project_id: str | None = None
    tasks_path: Path = PROJECT_ROOT / "tasks"  # every *.yaml in this directory
    bench_timeout_s: float = Field(default=30.0, gt=0)
