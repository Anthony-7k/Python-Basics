from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded exclusively from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_env: Literal["development", "test", "integration", "production"] = "development"
    log_level: str = "INFO"
    database_url: str = "sqlite:///./data/enterprise_agent.db"
    agent_max_steps: int = Field(default=10, ge=1, le=50)
    tool_timeout_seconds: float = Field(default=10.0, gt=0, le=120)
    tool_max_retries: int = Field(default=2, ge=0, le=5)

    planner_mode: Literal["rule_based", "openai"] = "rule_based"
    llm_api_key: SecretStr | None = None
    llm_base_url: str = "https://api.openai.com/v1"
    llm_model: str = "gpt-4.1-mini"
    llm_timeout_seconds: float = Field(default=30.0, gt=0, le=180)
    llm_max_retries: int = Field(default=2, ge=0, le=5)
    llm_input_cost_per_million: float | None = Field(default=None, ge=0)
    llm_output_cost_per_million: float | None = Field(default=None, ge=0)

    jwt_issuer: str = "enterprise-ai-agent"
    jwt_audience: str = "enterprise-ai-agent-api"
    jwt_algorithm: Literal["HS256", "RS256"] = "HS256"
    jwt_secret: SecretStr | None = SecretStr("development-only-change-me-32-bytes")
    jwt_public_key: SecretStr | None = None
    jwks_url: str | None = None
    jwt_token_ttl_seconds: int = Field(default=3600, ge=60, le=86400)
    allow_dev_identity: bool = True

    knowledge_backend: Literal["sample", "agent01"] = "sample"
    agent01_base_url: str = "http://127.0.0.1:8000"
    agent01_bearer_token: SecretStr | None = None
    agent01_knowledge_base_id: str | None = None
    knowledge_fallback_to_sample: bool = True

    cors_allowed_origins: str = "http://127.0.0.1:5173,http://localhost:5173"
    prometheus_enabled: bool = True

    api_port: int = Field(default=8001, ge=1, le=65535)

    @field_validator(
        "llm_input_cost_per_million",
        "llm_output_cost_per_million",
        mode="before",
    )
    @classmethod
    def empty_optional_cost_is_none(cls, value: object) -> object:
        """Allow optional cost fields to remain blank in environment files."""

        if isinstance(value, str) and not value.strip():
            return None
        return value

    @property
    def auto_create_schema(self) -> bool:
        """Only developer-friendly environments may bypass Alembic."""

        return self.app_env in {"development", "test"}

    @property
    def allowed_origins(self) -> list[str]:
        return [
            item.strip()
            for item in self.cors_allowed_origins.split(",")
            if item.strip()
        ]

    def validate_runtime(self) -> None:
        if self.app_env == "production" and self.allow_dev_identity:
            raise ValueError("ALLOW_DEV_IDENTITY must be false in production")
        if self.app_env == "production" and "*" in self.allowed_origins:
            raise ValueError("CORS_ALLOWED_ORIGINS must not contain * in production")
        if self.jwt_algorithm == "HS256" and not self.jwt_secret:
            raise ValueError("JWT_SECRET is required when JWT_ALGORITHM=HS256")
        if self.jwt_algorithm == "RS256" and not (self.jwt_public_key or self.jwks_url):
            raise ValueError(
                "JWT_PUBLIC_KEY or JWKS_URL is required when JWT_ALGORITHM=RS256"
            )
        if (
            self.app_env == "production"
            and self.jwt_algorithm == "HS256"
            and self.jwt_secret
            and self.jwt_secret.get_secret_value()
            == "development-only-change-me-32-bytes"
        ):
            raise ValueError("Production must replace the development JWT secret")
        if self.planner_mode == "openai" and not self.llm_api_key:
            raise ValueError("LLM_API_KEY is required when PLANNER_MODE=openai")
        if self.knowledge_backend == "agent01":
            if (
                self.app_env in {"integration", "production"}
                and self.knowledge_fallback_to_sample
            ):
                raise ValueError(
                    "KNOWLEDGE_FALLBACK_TO_SAMPLE must be false for agent01 "
                    "in integration and production"
                )
            missing = []
            if not self.agent01_bearer_token:
                missing.append("AGENT01_BEARER_TOKEN")
            if not self.agent01_knowledge_base_id:
                missing.append("AGENT01_KNOWLEDGE_BASE_ID")
            if missing and not self.knowledge_fallback_to_sample:
                raise ValueError("Missing agent01 settings: " + ", ".join(missing))


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.validate_runtime()
    return settings


def clear_settings_cache() -> None:
    get_settings.cache_clear()
