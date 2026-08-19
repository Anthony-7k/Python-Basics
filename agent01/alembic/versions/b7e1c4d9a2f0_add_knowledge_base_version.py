"""add knowledge base version

Revision ID: b7e1c4d9a2f0
Revises: 8a2d4e6f9c11
Create Date: 2026-08-18 23:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b7e1c4d9a2f0"
down_revision: Union[
    str,
    Sequence[str],
    None,
] = "8a2d4e6f9c11"
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
        "knowledge_bases",
        sa.Column(
            "version",
            sa.Integer(),
            server_default="1",
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column(
        "knowledge_bases",
        "version",
    )
