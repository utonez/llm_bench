"""Turn a targets YAML file + settings into runnable (provider, model) targets."""

import logging
from dataclasses import dataclass
from pathlib import Path

import httpx
import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.bench.runner import Target
from app.config import Settings
from app.providers.base import Provider
from app.providers.mock import MockProvider
from app.providers.openai_compat import OpenAICompatibleProvider

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ProviderSpec:
    base_url: str
    key_setting: str  # attribute name on Settings
    min_interval_s: float  # pacing between calls, kept under the free tier's RPM


# Pacing: the first cloud round sent 27 calls back to back and Gemini returned 429 on 10
# of them. Intervals keep each provider comfortably under its per-minute limit:
#   gemini 4.5 s ≈ 13 RPM · groq 2.5 s ≈ 24 RPM (30 RPM documented) · openrouter 3.5 s ≈ 17 RPM (20)
PROVIDERS: dict[str, ProviderSpec] = {
    "gemini": ProviderSpec(
        "https://generativelanguage.googleapis.com/v1beta/openai", "gemini_api_key", 4.5
    ),
    "groq": ProviderSpec("https://api.groq.com/openai/v1", "groq_api_key", 2.5),
    "openrouter": ProviderSpec("https://openrouter.ai/api/v1", "openrouter_api_key", 3.5),
}
MOCK = "mock"


class TargetConfigError(Exception):
    pass


class TargetSpec(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    provider: str
    model: str = Field(min_length=1)
    min_output_tokens: int = Field(default=0, ge=0, le=8192)
    price_ref: str | None = None  # OpenRouter model id used as the market reference price
    # mock-only options
    name: str | None = None
    seed: int = 0
    latency_s: float = Field(default=0.05, ge=0)
    failure_rate: float = Field(default=0.0, ge=0, le=1)


def load_target_specs(path: Path) -> list[TargetSpec]:
    if not path.is_file():
        raise TargetConfigError(f"targets file not found: {path}")
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    try:
        specs = [TargetSpec.model_validate(entry) for entry in raw.get("targets") or []]
    except ValidationError as exc:
        raise TargetConfigError(f"invalid target in {path}: {exc}") from exc
    unknown = sorted({s.provider for s in specs} - {*PROVIDERS, MOCK})
    if unknown:
        raise TargetConfigError(f"unknown provider(s) in {path}: {unknown}")
    return specs


def build_targets(settings: Settings, client: httpx.AsyncClient) -> list[Target]:
    providers: dict[str, Provider] = {}
    targets: list[Target] = []
    for spec in load_target_specs(settings.targets_path):
        provider = _provider_for(spec, settings, client, providers)
        if provider is not None:
            interval = (
                PROVIDERS[spec.provider].min_interval_s if spec.provider in PROVIDERS else 0.0
            )
            targets.append(
                Target(provider, spec.model, spec.min_output_tokens, interval, spec.price_ref)
            )
    if not targets:
        raise TargetConfigError(
            f"no usable targets in {settings.targets_path}: set API keys in .env, "
            "or use TARGETS_PATH=config/targets_mock.yaml"
        )
    return targets


def build_api_providers(
    settings: Settings, client: httpx.AsyncClient
) -> list[OpenAICompatibleProvider]:
    """Every real provider that has a key configured (used by jobs.list_models)."""
    return [
        OpenAICompatibleProvider(name, spec.base_url, key, client)
        for name, spec in PROVIDERS.items()
        if (key := _api_key(settings, spec)) is not None
    ]


def _provider_for(
    spec: TargetSpec, settings: Settings, client: httpx.AsyncClient, cache: dict[str, Provider]
) -> Provider | None:
    if spec.provider == MOCK:
        name = spec.name or f"mock-{spec.model}"
        if name not in cache:
            cache[name] = MockProvider(
                name=name, seed=spec.seed, latency_s=spec.latency_s, failure_rate=spec.failure_rate
            )
        return cache[name]

    if spec.provider not in cache:
        provider_spec = PROVIDERS[spec.provider]
        key = _api_key(settings, provider_spec)
        if key is None:
            logger.warning("skipping %s/%s: no API key configured", spec.provider, spec.model)
            return None
        cache[spec.provider] = OpenAICompatibleProvider(
            spec.provider, provider_spec.base_url, key, client
        )
    return cache[spec.provider]


def _api_key(settings: Settings, spec: ProviderSpec) -> str | None:
    secret = getattr(settings, spec.key_setting)
    return secret.get_secret_value() if secret is not None else None
