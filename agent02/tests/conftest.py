from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.database import Database
from app.main import create_app


@pytest.fixture
def settings() -> Settings:
    return Settings(
        database_url="sqlite://",
        planner_mode="rule_based",
        knowledge_backend="sample",
        tool_timeout_seconds=2.0,
        tool_max_retries=2,
        agent_max_steps=10,
        log_level="WARNING",
    )


@pytest.fixture
def database() -> Database:
    db = Database("sqlite://")
    db.create_all()
    yield db
    db.drop_all()


@pytest.fixture
def app(settings: Settings, database: Database):
    return create_app(settings, database)


@pytest.fixture
def client(app):
    with TestClient(app) as test_client:
        yield test_client


def chat_payload(
    message: str, *, user_id: str = "user-1", session_id: str = "session-1"
):
    return {"message": message, "user_id": user_id, "session_id": session_id}
