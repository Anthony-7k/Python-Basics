from __future__ import annotations

from pathlib import Path

import fitz
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.database import Database
from app.main import create_app


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        _env_file=None,
        app_env="test",
        secret_key="test-secret-that-is-more-than-thirty-two-bytes-long",
        database_url=f"sqlite:///{tmp_path / 'test.db'}",
        object_storage_path=tmp_path / "objects",
        auto_create_schema=True,
        seed_demo_data=True,
        task_queue_backend="eager",
        virus_scanner_backend="fake",
        ocr_backend="fake",
        extraction_backend="deterministic",
    )


@pytest.fixture
def database(settings: Settings) -> Database:
    return Database(settings.database_url)


@pytest.fixture
def app(settings: Settings, database: Database):
    return create_app(settings, database)


@pytest.fixture
def client(app):
    with TestClient(app) as value:
        yield value


@pytest.fixture
def token(client: TestClient) -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "demo@docflow.local", "password": "Demo123!"},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


@pytest.fixture
def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def pdf_bytes() -> bytes:
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), "Contract test document")
    data = document.tobytes()
    document.close()
    return data

