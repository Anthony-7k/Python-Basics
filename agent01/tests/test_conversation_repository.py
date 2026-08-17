import pytest

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.models import MessageRole
from app.repositories import (
    ConversationRepository,
)
from app.services.conversations import (
    ConversationService,
)

from app.core.exceptions import (
    ConversationNotFoundError,
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

    @event.listens_for(
        engine,
        "connect",
    )
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


def create_conversation_fixture(
    session: Session,
):
    repository = ConversationRepository(
        session
    )

    user = repository.create_user(
        email="day11@example.com",
        display_name="Day 11 User",
    )

    knowledge_base = (
        repository.create_knowledge_base(
            owner_user_id=user.id,
            name="Day 11 Knowledge Base",
        )
    )

    conversation = (
        repository.create_conversation(
            user_id=user.id,
            knowledge_base_id=(
                knowledge_base.id
            ),
            title="Repository Test",
        )
    )

    session.commit()

    return repository, conversation


def test_repository_saves_exchange(
    db_session: Session,
):
    repository, conversation = (
        create_conversation_fixture(
            db_session
        )
    )

    repository.add_message(
        conversation_id=conversation.id,
        role=MessageRole.USER,
        content="员工有多少天年假？",
    )

    repository.add_message(
        conversation_id=conversation.id,
        role=MessageRole.ASSISTANT,
        content="员工年假根据工龄确定。[S1]",
        source_summary={
            "sources": [
                {
                    "source_id": "S1",
                    "chunk_id": "chunk-1",
                }
            ]
        },
    )

    db_session.commit()

    messages = repository.list_messages(
        conversation.id
    )

    assert len(messages) == 2

    assert [
        message.sequence_number
        for message in messages
    ] == [1, 2]

    assert [
        message.role
        for message in messages
    ] == [
        MessageRole.USER,
        MessageRole.ASSISTANT,
    ]

    assert messages[1].source_summary == {
        "sources": [
            {
                "source_id": "S1",
                "chunk_id": "chunk-1",
            }
        ]
    }


def test_repository_transaction_rollback(
    db_session: Session,
):
    repository, conversation = (
        create_conversation_fixture(
            db_session
        )
    )

    repository.add_message(
        conversation_id=conversation.id,
        role=MessageRole.USER,
        content="这条消息应被回滚",
    )

    repository.add_message(
        conversation_id=conversation.id,
        role=MessageRole.ASSISTANT,
        content="这条回复也应被回滚",
    )

    db_session.rollback()

    messages = repository.list_messages(
        conversation.id
    )

    assert messages == []

def test_conversation_service_commits_exchange(
    db_session: Session,
):
    repository, conversation = (
        create_conversation_fixture(
            db_session
        )
    )

    service = ConversationService(
        db_session
    )

    service.save_exchange(
        conversation_id=conversation.id,
        user_content="员工有多少天年假？",
        assistant_content=(
            "员工年假根据工龄确定。[S1]"
        ),
        source_summary={
            "sources": [
                {
                    "source_id": "S1",
                    "chunk_id": "chunk-1",
                }
            ]
        },
    )

    messages = repository.list_messages(
        conversation.id
    )

    assert len(messages) == 2

    assert [
        message.sequence_number
        for message in messages
    ] == [1, 2]


def test_conversation_service_rolls_back_exchange(
    db_session: Session,
    monkeypatch,
):
    repository, conversation = (
        create_conversation_fixture(
            db_session
        )
    )

    service = ConversationService(
        db_session
    )

    original_add_message = (
        service.repository.add_message
    )

    def add_message_with_failure(
        *,
        conversation_id,
        role,
        content,
        source_summary=None,
    ):
        if role == MessageRole.ASSISTANT:
            raise RuntimeError(
                "assistant save failed"
            )

        return original_add_message(
            conversation_id=conversation_id,
            role=role,
            content=content,
            source_summary=source_summary,
        )

    monkeypatch.setattr(
        service.repository,
        "add_message",
        add_message_with_failure,
    )

    with pytest.raises(
        RuntimeError,
        match="assistant save failed",
    ):
        service.save_exchange(
            conversation_id=(
                conversation.id
            ),
            user_content="用户消息",
            assistant_content="助手消息",
        )

    messages = repository.list_messages(
        conversation.id
    )

    assert messages == []

def test_service_creates_default_conversation(
    db_session: Session,
):
    service = ConversationService(
        db_session
    )

    conversation = (
        service.get_or_create_conversation()
    )

    saved_conversation = (
        service.repository.get_conversation(
            conversation.id
        )
    )

    assert saved_conversation is not None

    assert (
        saved_conversation.id
        == conversation.id
    )

    assert (
        saved_conversation.user.email
        == "local-user@agent01.local"
    )

    assert (
        saved_conversation
        .knowledge_base.name
        == "Default Knowledge Base"
    )


def test_service_rejects_missing_conversation(
    db_session: Session,
):
    service = ConversationService(
        db_session
    )

    with pytest.raises(
        ConversationNotFoundError,
    ):
        service.get_or_create_conversation(
            conversation_id=(
                "missing-conversation"
            )
        )