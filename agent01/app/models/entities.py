from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import uuid4

from sqlalchemy import (
    JSON,
    DateTime,
    Enum as SQLAlchemyEnum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
)

from app.db.base import Base


def generate_uuid() -> str:
    return str(uuid4())


def enum_values(enum_class):
    return [
        item.value
        for item in enum_class
    ]


class DocumentStatus(str, Enum):
    PENDING = "pending"
    READY = "ready"
    FAILED = "failed"
    DELETED = "deleted"


class IngestionJobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=generate_uuid,
    )

    email: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        index=True,
    )

    display_name: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    knowledge_bases: Mapped[
        list[KnowledgeBase]
    ] = relationship(
        back_populates="owner",
    )

    conversations: Mapped[
        list[Conversation]
    ] = relationship(
        back_populates="user",
    )


class KnowledgeBase(TimestampMixin, Base):
    __tablename__ = "knowledge_bases"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=generate_uuid,
    )

    owner_user_id: Mapped[str] = mapped_column(
        ForeignKey(
            "users.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    owner: Mapped[User] = relationship(
        back_populates="knowledge_bases",
    )

    documents: Mapped[
        list[Document]
    ] = relationship(
        back_populates="knowledge_base",
    )

    conversations: Mapped[
        list[Conversation]
    ] = relationship(
        back_populates="knowledge_base",
    )


class Document(TimestampMixin, Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
    )

    knowledge_base_id: Mapped[str] = mapped_column(
        ForeignKey(
            "knowledge_bases.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )

    file_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    content_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
        index=True,
    )

    status: Mapped[DocumentStatus] = mapped_column(
        SQLAlchemyEnum(
            DocumentStatus,
            values_callable=enum_values,
            native_enum=False,
            length=20,
        ),
        nullable=False,
        default=DocumentStatus.PENDING,
        server_default=DocumentStatus.PENDING.value,
    )

    knowledge_base: Mapped[
        KnowledgeBase
    ] = relationship(
        back_populates="documents",
    )

    ingestion_jobs: Mapped[
        list[IngestionJob]
    ] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class Conversation(TimestampMixin, Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=generate_uuid,
    )

    user_id: Mapped[str] = mapped_column(
        ForeignKey(
            "users.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )

    knowledge_base_id: Mapped[str] = mapped_column(
        ForeignKey(
            "knowledge_bases.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )

    title: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    summary: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    summary_through_sequence_number: Mapped[
        int
    ] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    summary_updated_at: Mapped[
        datetime | None
    ] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    user: Mapped[User] = relationship(
        back_populates="conversations",
    )

    knowledge_base: Mapped[
        KnowledgeBase
    ] = relationship(
        back_populates="conversations",
    )

    messages: Mapped[
        list[Message]
    ] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="Message.sequence_number",
    )


class Message(Base):
    __tablename__ = "messages"

    __table_args__ = (
        UniqueConstraint(
            "conversation_id",
            "sequence_number",
            name=(
                "uq_messages_"
                "conversation_sequence"
            ),
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=generate_uuid,
    )

    conversation_id: Mapped[str] = mapped_column(
        ForeignKey(
            "conversations.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    sequence_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    role: Mapped[MessageRole] = mapped_column(
        SQLAlchemyEnum(
            MessageRole,
            values_callable=enum_values,
            native_enum=False,
            length=20,
        ),
        nullable=False,
    )

    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    source_summary: Mapped[
        dict | None
    ] = mapped_column(
        JSON,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )

    conversation: Mapped[
        Conversation
    ] = relationship(
        back_populates="messages",
    )


class IngestionJob(TimestampMixin, Base):
    __tablename__ = "ingestion_jobs"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=generate_uuid,
    )

    document_id: Mapped[str] = mapped_column(
        ForeignKey(
            "documents.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    status: Mapped[
        IngestionJobStatus
    ] = mapped_column(
        SQLAlchemyEnum(
            IngestionJobStatus,
            values_callable=enum_values,
            native_enum=False,
            length=20,
        ),
        nullable=False,
        default=IngestionJobStatus.PENDING,
        server_default=(
            IngestionJobStatus.PENDING.value
        ),
    )

    error: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    document: Mapped[
        Document
    ] = relationship(
        back_populates="ingestion_jobs",
    )
