"""Runtime settings, read from environment variables (and .env locally)."""

from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    storage_backend: Literal["memory", "firestore"] = "memory"
    gcp_project_id: str | None = None
    tasks_path: Path = PROJECT_ROOT / "tasks"  # every *.yaml in this directory
    targets_path: Path = PROJECT_ROOT / "config" / "targets.yaml"
    bench_timeout_s: float = Field(default=30.0, gt=0)
    pricing_enabled: bool = True  # fetch OpenRouter prices + Central Bank FX each round

    # Query API (public, read-only)
    allowed_origins: list[str] = []  # CORS: the dashboard origin(s); empty = same-origin only
    api_rate_limit_per_minute: int = Field(default=120, ge=1)
    api_cache_ttl_s: float = Field(default=300.0, ge=0)
    frontend_dir: Path = PROJECT_ROOT / "frontend"  # served at "/" when it exists

    # Provider keys: .env locally, Secret Manager in the cloud. Never logged (SecretStr).
    gemini_api_key: SecretStr | None = None
    groq_api_key: SecretStr | None = None
    openrouter_api_key: SecretStr | None = None
