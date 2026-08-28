"""add message sequence number

Revision ID: 7af58a1df946
Revises: 3c1068922c5b
Create Date: 2026-08-17 15:12:47.511845

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7af58a1df946'
down_revision: Union[str, Sequence[str], None] = '3c1068922c5b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    column_names = {
        column["name"]
        for column in inspector.get_columns("messages")
    }
    if "sequence_number" not in column_names:
        op.add_column(
            "messages",
            sa.Column(
                "sequence_number",
                sa.Integer(),
                nullable=False,
            ),
        )

    inspector = sa.inspect(bind)
    constraint_names = {
        constraint["name"]
        for constraint in inspector.get_unique_constraints(
            "messages"
        )
    }
    if (
        "uq_messages_conversation_sequence"
        not in constraint_names
    ):
        op.create_unique_constraint(
            "uq_messages_conversation_sequence",
            "messages",
            ["conversation_id", "sequence_number"],
        )


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    constraint_names = {
        constraint["name"]
        for constraint in inspector.get_unique_constraints(
            "messages"
        )
    }
    if "uq_messages_conversation_sequence" in constraint_names:
        op.drop_constraint(
            "uq_messages_conversation_sequence",
            "messages",
            type_="unique",
        )

    inspector = sa.inspect(bind)
    column_names = {
        column["name"]
        for column in inspector.get_columns("messages")
    }
    if "sequence_number" in column_names:
        op.drop_column("messages", "sequence_number")
