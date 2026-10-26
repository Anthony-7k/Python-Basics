from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_SECRET = "change-this-in-non-development-environments"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    secret_key: str = DEFAULT_SECRET
    database_url: str = "sqlite:///./data/docflow.db"
    public_base_url: str = "http://127.0.0.1:8003"
    allowed_origins: str = "http://127.0.0.1:5173,http://localhost:5173"
    access_token_minutes: int = 60
    selection_token_minutes: int = 5
    auto_create_schema: bool = True
    seed_demo_data: bool = True
    object_storage_backend: str = "filesystem"
    object_storage_path: Path = Path("./data/objects")
    s3_endpoint: str = "http://minio:9000"
    s3_bucket: str = "docflow"
    s3_access_key: str = "docflow"
    s3_secret_key: str = "change-me"
    virus_scanner_backend: str = "fake"
    report_renderer_backend: str = "pymupdf"
    task_queue_backend: str = "eager"
    celery_broker_url: str = "redis://redis:6379/0"
    celery_result_backend: str = "redis://redis:6379/1"
    max_upload_bytes: int = 25 * 1024 * 1024
    log_level: str = "INFO"
    metrics_enabled: bool = True
    ocr_backend: str = "fake"
    extraction_backend: str = "deterministic"
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = ""
    model_timeout_seconds: float = 90
    model_retries: int = 1
    cloud_model_base_url: str = ""
    cloud_model_name: str = ""
    cloud_model_api_key: SecretStr = SecretStr("")
    cloud_model_provider: str = "generic"

    @property
    def allowed_origin_list(self) -> list[str]:
        return [part.strip() for part in self.allowed_origins.split(",") if part.strip()]

    def validate_runtime(self) -> None:
        if self.cloud_model_provider not in {"generic", "dashscope"}:
            raise ValueError("unsupported cloud model provider")
        if self.ocr_backend not in {"fake", "rapidocr"}:
            raise ValueError("unsupported OCR backend")
        if self.extraction_backend not in {"deterministic", "ollama", "cloud"}:
            raise ValueError("unsupported extraction backend")
        if self.extraction_backend == "ollama" and not self.ollama_model.strip():
            raise ValueError("OLLAMA_MODEL is required for model extraction")
        if self.extraction_backend == "cloud":
            url = urlsplit(self.cloud_model_base_url)
            if (url.scheme != "https" or not url.hostname or url.username or url.password
                    or url.query or url.fragment or any(char in self.cloud_model_base_url for char in "{}<>")
                    or "workspaceid" in url.hostname.lower()):
                raise ValueError("CLOUD_MODEL_BASE_URL must be an HTTPS service endpoint")
            if not self.cloud_model_name.strip() or not self.cloud_model_api_key.get_secret_value():
                raise ValueError("cloud model name and API key are required")
        if not 1 <= self.model_timeout_seconds <= 300 or not 0 <= self.model_retries <= 2:
            raise ValueError("model timeout or retries outside supported bounds")
        if self.app_env not in {"development", "test"} and self.secret_key == DEFAULT_SECRET:
            raise ValueError("SECRET_KEY must be changed outside development and test")
        if self.app_env == "production":
            if self.virus_scanner_backend == "fake":
                raise ValueError("Fake virus scanner is forbidden outside development and test")
            if self.task_queue_backend == "eager":
                raise ValueError("Eager task queue is forbidden outside development and test")
            if self.ocr_backend == "fake":
                raise ValueError("Fake OCR is forbidden in production")


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.validate_runtime()
    return settings

