"""versioned policies, searchable chunks, and risk citations"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "20260928_0005"
down_revision = "20260928_0004"
branch_labels = None
depends_on = None


def _tables() -> set[str]:
    return set(inspect(op.get_bind()).get_table_names())


def _columns(table: str) -> set[str]:
    return {column["name"] for column in inspect(op.get_bind()).get_columns(table)}


def _indexes(table: str, columns: tuple[str, ...]) -> None:
    for column in columns:
        op.create_index(f"ix_{table}_{column}", table, [column])


def upgrade() -> None:
    tables = _tables()
    if "policy_documents" not in tables:
        op.create_table(
            "policy_documents",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False),
            sa.Column("title", sa.String(300), nullable=False),
            sa.Column("version", sa.String(100), nullable=False),
            sa.Column("status", sa.String(30), nullable=False),
            sa.Column("effective_on", sa.Date(), nullable=False),
            sa.Column("expires_on", sa.Date(), nullable=True),
            sa.Column("original_name", sa.String(500), nullable=False),
            sa.Column("object_key", sa.String(500), nullable=False, unique=True),
            sa.Column("content_hash", sa.String(64), nullable=False),
            sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("tenant_id", "title", "version", name="uq_policy_title_version"),
            sa.UniqueConstraint("tenant_id", "content_hash", name="uq_policy_content_hash"),
        )
        _indexes(
            "policy_documents",
            ("tenant_id", "title", "status", "effective_on", "expires_on"),
        )
    if "policy_chunks" not in tables:
        op.create_table(
            "policy_chunks",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False),
            sa.Column("policy_document_id", sa.String(36), sa.ForeignKey("policy_documents.id"), nullable=False),
            sa.Column("chunk_index", sa.Integer(), nullable=False),
            sa.Column("page_number", sa.Integer(), nullable=False),
            sa.Column("heading", sa.String(500), nullable=False),
            sa.Column("text", sa.Text(), nullable=False),
            sa.Column("text_hash", sa.String(64), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("policy_document_id", "chunk_index", name="uq_policy_chunk_index"),
        )
        _indexes("policy_chunks", ("tenant_id", "policy_document_id"))
    if "policy_citations" not in _columns("risk_findings"):
        op.add_column(
            "risk_findings",
            sa.Column(
                "policy_citations",
                sa.JSON(),
                nullable=False,
                server_default=sa.text("'[]'"),
            ),
        )


def downgrade() -> None:
    if "policy_citations" in _columns("risk_findings"):
        op.drop_column("risk_findings", "policy_citations")
    for table in ("policy_chunks", "policy_documents"):
        if table in _tables():
            op.drop_table(table)
