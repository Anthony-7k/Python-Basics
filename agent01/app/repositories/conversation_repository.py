from datetime import datetime, timezone

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.models import (
    Conversation,
    KnowledgeBase,
    Message,
    MessageRole,
    User,
)


class ConversationRepository:
    def __init__(
        self,
        session: Session,
    ) -> None:
        self.session = session

    def create_user(
        self,
        email: str,
        display_name: str | None = None,
    ) -> User:
        existing_user = self.session.scalar(
            select(User).where(
                User.email == email
            )
        )

        if existing_user is not None:
            return existing_user

        user = User(
            email=email,
            display_name=display_name,
        )

        self.session.add(user)
        self.session.flush()

        return user

    def create_knowledge_base(
        self,
        owner_user_id: str,
        name: str,
        description: str | None = None,
    ) -> KnowledgeBase:
        knowledge_base = KnowledgeBase(
            owner_user_id=owner_user_id,
            name=name,
            description=description,
        )

        self.session.add(knowledge_base)
        self.session.flush()

        return knowledge_base

    def get_knowledge_base(
        self,
        knowledge_base_id: str,
    ) -> KnowledgeBase | None:
        return self.session.get(
            KnowledgeBase,
            knowledge_base_id,
        )

    def list_knowledge_bases(
        self,
        owner_user_id: str,
    ) -> list[KnowledgeBase]:
        statement = (
            select(KnowledgeBase)
            .where(
                KnowledgeBase.owner_user_id
                == owner_user_id
            )
            .order_by(
                KnowledgeBase.created_at,
                KnowledgeBase.id,
            )
        )

        return list(
            self.session.scalars(
                statement
            ).all()
        )

    def increment_knowledge_base_version(
        self,
        knowledge_base_id: str,
    ) -> KnowledgeBase | None:
        knowledge_base = self.session.scalar(
            select(KnowledgeBase)
            .where(
                KnowledgeBase.id
                == knowledge_base_id
            )
            .with_for_update()
        )

        if knowledge_base is None:
            return None

        knowledge_base.version += 1
        self.session.flush()

        return knowledge_base

    def get_or_create_knowledge_base(
        self,
        owner_user_id: str,
        name: str,
    ) -> KnowledgeBase:
        existing_knowledge_base = (
            self.session.scalar(
                select(KnowledgeBase).where(
                    KnowledgeBase.owner_user_id
                    == owner_user_id,
                    KnowledgeBase.name == name,
                )
            )
        )

        if (
            existing_knowledge_base
            is not None
        ):
            return existing_knowledge_base

        return self.create_knowledge_base(
            owner_user_id=owner_user_id,
            name=name,
        )

    def create_conversation(
        self,
        user_id: str,
        knowledge_base_id: str,
        title: str | None = None,
    ) -> Conversation:
        conversation = Conversation(
            user_id=user_id,
            knowledge_base_id=(
                knowledge_base_id
            ),
            title=title,
        )

        self.session.add(conversation)
        self.session.flush()

        return conversation

    def get_conversation(
        self,
        conversation_id: str,
    ) -> Conversation | None:
        return self.session.get(
            Conversation,
            conversation_id,
        )

    def add_message(
        self,
        conversation_id: str,
        role: MessageRole,
        content: str,
        source_summary: dict | None = None,
    ) -> Message:
        conversation = self.session.scalar(
            select(Conversation)
            .where(
                Conversation.id
                == conversation_id
            )
            .with_for_update()
        )

        if conversation is None:
            raise ValueError(
                "Conversation not found"
            )

        last_sequence_number = (
            self.session.scalar(
                select(
                    func.max(
                        Message.sequence_number
                    )
                ).where(
                    Message.conversation_id
                    == conversation_id
                )
            )
            or 0
        )

        message = Message(
            conversation_id=conversation_id,
            sequence_number=(
                last_sequence_number + 1
            ),
            role=role,
            content=content,
            source_summary=source_summary,
        )

        self.session.add(message)
        self.session.flush()

        return message

    def list_messages(
        self,
        conversation_id: str,
    ) -> list[Message]:
        statement = (
            select(Message)
            .where(
                Message.conversation_id
                == conversation_id
            )
            .order_by(
                Message.sequence_number
            )
        )

        return list(
            self.session.scalars(
                statement
            ).all()
        )

    def list_recent_messages(
        self,
        conversation_id: str,
        limit: int,
    ) -> list[Message]:
        if limit < 1:
            return []

        statement = (
            select(Message)
            .where(
                Message.conversation_id
                == conversation_id
            )
            .order_by(
                desc(
                    Message.sequence_number
                )
            )
            .limit(limit)
        )

        messages = list(
            self.session.scalars(
                statement
            ).all()
        )

        messages.reverse()

        return messages

    def list_messages_for_summary(
        self,
        conversation_id: str,
        after_sequence_number: int,
        through_sequence_number: int,
        limit: int,
    ) -> list[Message]:
        statement = (
            select(Message)
            .where(
                Message.conversation_id
                == conversation_id,
                Message.sequence_number
                > after_sequence_number,
                Message.sequence_number
                <= through_sequence_number,
            )
            .order_by(
                Message.sequence_number
            )
            .limit(limit)
        )

        return list(
            self.session.scalars(
                statement
            ).all()
        )

    def update_summary(
        self,
        conversation: Conversation,
        summary: str,
        through_sequence_number: int,
    ) -> None:
        conversation.summary = summary
        conversation.summary_through_sequence_number = (
            through_sequence_number
        )
        conversation.summary_updated_at = (
            datetime.now(timezone.utc)
        )

        self.session.flush()
