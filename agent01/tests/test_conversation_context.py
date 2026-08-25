import pytest

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.core.security import AuthenticatedUser
from app.models import MessageRole
from app.repositories import (
    ConversationRepository,
)
from app.services.conversations import (
    ConversationService,
)


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={
            "check_same_thread": False,
        },
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(
        dbapi_connection,
        connection_record,
    ):
        cursor = dbapi_connection.cursor()
        cursor.execute(
            "PRAGMA foreign_keys=ON"
        )
        cursor.close()

    Base.metadata.create_all(engine)

    with Session(
        engine,
        expire_on_commit=False,
    ) as session:
        yield session

    Base.metadata.drop_all(engine)
    engine.dispose()


def create_history(
    session: Session,
    exchange_count: int,
):
    repository = ConversationRepository(
        session
    )
    user = repository.create_user(
        email="day12@example.com"
    )
    knowledge_base = (
        repository.create_knowledge_base(
            owner_user_id=user.id,
            name="Day 12 Knowledge Base",
        )
    )
    conversation = (
        repository.create_conversation(
            user_id=user.id,
            knowledge_base_id=(
                knowledge_base.id
            ),
        )
    )

    for index in range(exchange_count):
        repository.add_message(
            conversation_id=conversation.id,
            role=MessageRole.USER,
            content=f"问题 {index + 1}",
        )
        repository.add_message(
            conversation_id=conversation.id,
            role=MessageRole.ASSISTANT,
            content=f"回答 {index + 1}",
        )

    session.commit()

    return conversation


def test_prepare_context_keeps_recent_turns_and_summarizes_once(
    db_session,
    monkeypatch,
):
    conversation = create_history(
        db_session,
        exchange_count=4,
    )
    calls = []

    def fake_summarize(
        existing_summary,
        messages,
        token_budget,
    ):
        calls.append(messages)
        return "已总结问题 1 和问题 2"

    monkeypatch.setattr(
        "app.services.conversations."
        "conversation_service."
        "summarize_conversation",
        fake_summarize,
    )

    service = ConversationService(
        db_session,
        current_user=AuthenticatedUser(
            email="day12@example.com"
        ),
    )
    context = service.prepare_context(
        conversation.id,
        max_turns=2,
        token_budget=200,
    )

    assert [
        item["sequence_number"]
        for item in context.history
    ] == [5, 6, 7, 8]
    assert context.summary == (
        "已总结问题 1 和问题 2"
    )
    assert (
        conversation
        .summary_through_sequence_number
        == 4
    )
    assert len(calls) == 1

    service.prepare_context(
        conversation.id,
        max_turns=2,
        token_budget=200,
    )

    assert len(calls) == 1


def test_summary_failure_keeps_bounded_recent_history(
    db_session,
    monkeypatch,
):
    conversation = create_history(
        db_session,
        exchange_count=3,
    )

    def failed_summarize(
        existing_summary,
        messages,
        token_budget,
    ):
        raise RuntimeError("summary failed")

    monkeypatch.setattr(
        "app.services.conversations."
        "conversation_service."
        "summarize_conversation",
        failed_summarize,
    )

    context = ConversationService(
        db_session,
        current_user=AuthenticatedUser(
            email="day12@example.com"
        ),
    ).prepare_context(
        conversation.id,
        max_turns=1,
        token_budget=100,
    )

    assert [
        item["sequence_number"]
        for item in context.history
    ] == [5, 6]
    assert context.summary is None
    assert (
        conversation
        .summary_through_sequence_number
        == 0
    )
