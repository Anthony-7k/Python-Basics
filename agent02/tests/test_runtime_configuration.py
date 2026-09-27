from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr, ValidationError
from sqlalchemy import inspect

from app.config import Settings
from app.database import Database
from app.main import create_app


def test_schema_auto_create_is_limited_to_developer_environments():
    assert Settings(app_env="development").auto_create_schema is True
    assert Settings(app_env="test").auto_create_schema is True
    assert Settings(app_env="integration").auto_create_schema is False
    assert Settings(app_env="production").auto_create_schema is False


def test_unknown_environment_is_rejected():
    with pytest.raises(ValidationError):
        Settings(app_env="docker")


def test_blank_optional_llm_costs_are_treated_as_unset():
    settings = Settings(
        llm_input_cost_per_million="",  # type: ignore[arg-type]
        llm_output_cost_per_million="   ",  # type: ignore[arg-type]
    )

    assert settings.llm_input_cost_per_million is None
    assert settings.llm_output_cost_per_million is None


def test_production_rejects_wildcard_cors():
    settings = Settings(
        app_env="production",
        allow_dev_identity=False,
        jwt_secret="production-test-secret-at-least-32-bytes",
        cors_allowed_origins="*",
    )
    with pytest.raises(ValueError, match="CORS_ALLOWED_ORIGINS"):
        settings.validate_runtime()


def test_production_startup_does_not_create_schema(tmp_path):
    database = Database(f"sqlite:///{(tmp_path / 'production.db').as_posix()}")
    settings = Settings(
        app_env="production",
        allow_dev_identity=False,
        jwt_secret="production-test-secret",
        database_url=str(database.engine.url),
        planner_mode="rule_based",
        knowledge_backend="sample",
        log_level="WARNING",
    )

    with TestClient(create_app(settings, database)) as client:
        assert client.get("/live").status_code == 200

    assert inspect(database.engine).get_table_names() == []


def test_readiness_returns_503_when_database_is_unavailable(settings):
    class UnavailableDatabase:
        def check_connection(self) -> None:
            raise RuntimeError("database offline")

    production_settings = settings.model_copy(
        update={
            "app_env": "production",
            "allow_dev_identity": False,
            "jwt_secret": SecretStr("production-test-secret-at-least-32-bytes"),
        }
    )
    app = create_app(production_settings, UnavailableDatabase())

    with TestClient(app) as client:
        response = client.get("/ready", headers={"X-Request-ID": "req-not-ready"})

    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "request_id": "req-not-ready",
        "database": "unavailable",
    }


def test_integration_keeps_legacy_health_endpoint(settings, database):
    integration_settings = settings.model_copy(update={"app_env": "integration"})

    with TestClient(create_app(integration_settings, database)) as client:
        response = client.get(
            "/api/v1/health",
            headers={"X-Request-ID": "req-legacy-health"},
        )

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "request_id": "req-legacy-health",
        "database": "ok",
    }
