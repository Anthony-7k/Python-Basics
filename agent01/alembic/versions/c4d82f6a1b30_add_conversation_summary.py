"""add conversation summary fields

Revision ID: c4d82f6a1b30
Revises: 7af58a1df946
Create Date: 2026-08-18 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c4d82f6a1b30"
down_revision: Union[str, Sequence[str], None] = (
    "7af58a1df946"
)
branch_labels: Union[
    str,
    Sequence[str],
    None,
] = None
depends_on: Union[
    str,
    Sequence[str],
    None,
] = None


def upgrade() -> None:
    op.add_column(
        "conversations",
        sa.Column(
            "summary",
            sa.Text(),
            nullable=True,
        ),
    )
    op.add_column(
        "conversations",
        sa.Column(
            "summary_through_sequence_number",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "conversations",
        sa.Column(
            "summary_updated_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column(
        "conversations",
        "summary_updated_at",
    )
    op.drop_column(
        "conversations",
        "summary_through_sequence_number",
    )
    op.drop_column(
        "conversations",
        "summary",
    )
