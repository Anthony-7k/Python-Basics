"""document intelligence schema"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "20260927_0002"
down_revision = "20260927_0001"
branch_labels = None
depends_on = None


def _tables() -> set[str]:
    return set(inspect(op.get_bind()).get_table_names())


def _columns(table: str) -> set[str]:
    return {column["name"] for column in inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    columns = _columns("documents")
    additions = {
        "parse_status": sa.Column(
            "parse_status", sa.String(30), nullable=False, server_default="PENDING"
        ),
        "classification": sa.Column("classification", sa.String(50), nullable=True),
        "classification_confidence": sa.Column(
            "classification_confidence", sa.Float(), nullable=True
        ),
        "page_count": sa.Column("page_count", sa.Integer(), nullable=True),
    }
    for name, column in additions.items():
        if name not in columns:
            op.add_column("documents", column)

    tables = _tables()
    if "document_pages" not in tables:
        op.create_table(
            "document_pages",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False),
            sa.Column(
                "document_id", sa.String(36), sa.ForeignKey("documents.id"), nullable=False
            ),
            sa.Column("page_number", sa.Integer(), nullable=False),
            sa.Column("text", sa.Text(), nullable=False),
            sa.Column("width", sa.Float(), nullable=False),
            sa.Column("height", sa.Float(), nullable=False),
            sa.Column("blocks", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("document_id", "page_number", name="uq_document_page"),
        )
        op.create_index("ix_document_pages_tenant_id", "document_pages", ["tenant_id"])
        op.create_index("ix_document_pages_document_id", "document_pages", ["document_id"])
    if "extraction_runs" not in tables:
        op.create_table(
            "extraction_runs",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False),
            sa.Column(
                "document_id", sa.String(36), sa.ForeignKey("documents.id"), nullable=False
            ),
            sa.Column("status", sa.String(30), nullable=False),
            sa.Column("extractor_version", sa.String(50), nullable=False),
            sa.Column("schema_version", sa.String(50), nullable=False),
            sa.Column("classification", sa.String(50), nullable=True),
            sa.Column("classification_confidence", sa.Float(), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index("ix_extraction_runs_tenant_id", "extraction_runs", ["tenant_id"])
        op.create_index("ix_extraction_runs_document_id", "extraction_runs", ["document_id"])
    if "evidence_refs" not in tables:
        op.create_table(
            "evidence_refs",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False),
            sa.Column(
                "document_id", sa.String(36), sa.ForeignKey("documents.id"), nullable=False
            ),
            sa.Column("page_number", sa.Integer(), nullable=False),
            sa.Column("bbox", sa.JSON(), nullable=False),
            sa.Column("text_hash", sa.String(64), nullable=False),
            sa.Column("snippet", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_evidence_refs_tenant_id", "evidence_refs", ["tenant_id"])
        op.create_index("ix_evidence_refs_document_id", "evidence_refs", ["document_id"])
    if "field_values" not in tables:
        op.create_table(
            "field_values",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False),
            sa.Column(
                "document_id", sa.String(36), sa.ForeignKey("documents.id"), nullable=False
            ),
            sa.Column(
                "extraction_run_id",
                sa.String(36),
                sa.ForeignKey("extraction_runs.id"),
                nullable=False,
            ),
            sa.Column(
                "evidence_id", sa.String(36), sa.ForeignKey("evidence_refs.id"), nullable=False
            ),
            sa.Column("field_name", sa.String(100), nullable=False),
            sa.Column("raw_value", sa.Text(), nullable=False),
            sa.Column("normalized_value", sa.Text(), nullable=False),
            sa.Column("confidence", sa.Float(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_field_values_tenant_id", "field_values", ["tenant_id"])
        op.create_index("ix_field_values_document_id", "field_values", ["document_id"])
        op.create_index(
            "ix_field_values_extraction_run_id", "field_values", ["extraction_run_id"]
        )
        op.create_index("ix_field_values_field_name", "field_values", ["field_name"])


def downgrade() -> None:
    for table in ("field_values", "evidence_refs", "extraction_runs", "document_pages"):
        if table in _tables():
            op.drop_table(table)
    for column in ("page_count", "classification_confidence", "classification", "parse_status"):
        if column in _columns("documents"):
            op.drop_column("documents", column)

