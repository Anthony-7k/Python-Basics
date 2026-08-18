"""enable utf8mb4 for business tables

Revision ID: e91a7c3f2b64
Revises: c4d82f6a1b30
Create Date: 2026-08-18 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e91a7c3f2b64"
down_revision: Union[str, Sequence[str], None] = (
    "c4d82f6a1b30"
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


BUSINESS_TABLES = (
    "users",
    "knowledge_bases",
    "documents",
    "ingestion_jobs",
    "conversations",
    "messages",
)


def upgrade() -> None:
    bind = op.get_bind()
    database_name = bind.scalar(
        sa.text("SELECT DATABASE()")
    )

    if not database_name:
        raise RuntimeError(
            "No active MySQL database"
        )

    preparer = (
        bind.dialect.identifier_preparer
    )
    quoted_database = preparer.quote(
        database_name
    )

    op.execute(
        sa.text(
            f"ALTER DATABASE {quoted_database} "
            "CHARACTER SET utf8mb4 "
            "COLLATE utf8mb4_unicode_ci"
        )
    )

    op.execute(
        sa.text("SET FOREIGN_KEY_CHECKS = 0")
    )

    try:
        for table_name in BUSINESS_TABLES:
            quoted_table = preparer.quote(
                table_name
            )
            op.execute(
                sa.text(
                    f"ALTER TABLE {quoted_table} "
                    "CONVERT TO CHARACTER SET "
                    "utf8mb4 COLLATE "
                    "utf8mb4_unicode_ci"
                )
            )
    finally:
        op.execute(
            sa.text(
                "SET FOREIGN_KEY_CHECKS = 1"
            )
        )


def downgrade() -> None:
    raise RuntimeError(
        "Downgrading utf8mb4 is unsafe because "
        "it could corrupt stored Unicode text"
    )
