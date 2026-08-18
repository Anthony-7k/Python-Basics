"""scope document hash to knowledge base

Revision ID: 8a2d4e6f9c11
Revises: e91a7c3f2b64
Create Date: 2026-08-18 16:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "8a2d4e6f9c11"
down_revision: Union[
    str,
    Sequence[str],
    None,
] = "e91a7c3f2b64"
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
    connection = op.get_bind()
    duplicate_job_documents = (
        connection.scalar(
            sa.text(
                "SELECT COUNT(*) FROM ("
                "SELECT document_id "
                "FROM ingestion_jobs "
                "GROUP BY document_id "
                "HAVING COUNT(*) > 1"
                ") AS duplicate_jobs"
            )
        )
        or 0
    )
    if duplicate_job_documents:
        raise RuntimeError(
            "Cannot add ingestion attempt numbers: "
            "existing documents have multiple jobs"
        )

    op.drop_index(
        "ix_documents_content_hash",
        table_name="documents",
    )
    op.create_index(
        "ix_documents_content_hash",
        "documents",
        ["content_hash"],
        unique=False,
    )
    op.create_unique_constraint(
        "uq_documents_knowledge_base_content_hash",
        "documents",
        [
            "knowledge_base_id",
            "content_hash",
        ],
    )
    op.add_column(
        "ingestion_jobs",
        sa.Column(
            "attempt_number",
            sa.Integer(),
            server_default="1",
            nullable=False,
        ),
    )
    op.create_unique_constraint(
        "uq_ingestion_jobs_document_attempt",
        "ingestion_jobs",
        ["document_id", "attempt_number"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_ingestion_jobs_document_attempt",
        "ingestion_jobs",
        type_="unique",
    )
    op.drop_column(
        "ingestion_jobs",
        "attempt_number",
    )
    op.drop_constraint(
        "uq_documents_knowledge_base_content_hash",
        "documents",
        type_="unique",
    )
    op.drop_index(
        "ix_documents_content_hash",
        table_name="documents",
    )
    op.create_index(
        "ix_documents_content_hash",
        "documents",
        ["content_hash"],
        unique=True,
    )
