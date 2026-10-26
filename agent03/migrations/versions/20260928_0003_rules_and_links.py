"""document links and deterministic review rules"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "20260928_0003"
down_revision = "20260927_0002"
branch_labels = None
depends_on = None


def _tables() -> set[str]:
    return set(inspect(op.get_bind()).get_table_names())


def _indexes(table: str, columns: tuple[str, ...]) -> None:
    for column in columns:
        op.create_index(f"ix_{table}_{column}", table, [column])


def upgrade() -> None:
    tables = _tables()
    if "document_links" not in tables:
        op.create_table(
            "document_links",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False),
            sa.Column("case_id", sa.String(36), sa.ForeignKey("review_cases.id"), nullable=False),
            sa.Column("run_group_id", sa.String(36), nullable=False),
            sa.Column("source_document_id", sa.String(36), sa.ForeignKey("documents.id"), nullable=False),
            sa.Column("target_document_id", sa.String(36), sa.ForeignKey("documents.id"), nullable=False),
            sa.Column("link_type", sa.String(50), nullable=False),
            sa.Column("score", sa.Float(), nullable=False),
            sa.Column("evidence", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
        _indexes("document_links", ("tenant_id", "case_id", "run_group_id", "source_document_id", "target_document_id"))
    if "rule_runs" not in tables:
        op.create_table(
            "rule_runs",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False),
            sa.Column("case_id", sa.String(36), sa.ForeignKey("review_cases.id"), nullable=False),
            sa.Column("run_group_id", sa.String(36), nullable=False),
            sa.Column("rule_code", sa.String(100), nullable=False),
            sa.Column("rule_version", sa.String(30), nullable=False),
            sa.Column("outcome", sa.String(30), nullable=False),
            sa.Column("severity", sa.String(20), nullable=False),
            sa.Column("explanation", sa.Text(), nullable=False),
            sa.Column("inputs", sa.JSON(), nullable=False),
            sa.Column("evidence_ids", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
        _indexes("rule_runs", ("tenant_id", "case_id", "run_group_id", "rule_code"))
    if "risk_findings" not in tables:
        op.create_table(
            "risk_findings",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False),
            sa.Column("case_id", sa.String(36), sa.ForeignKey("review_cases.id"), nullable=False),
            sa.Column("rule_run_id", sa.String(36), sa.ForeignKey("rule_runs.id"), nullable=False),
            sa.Column("run_group_id", sa.String(36), nullable=False),
            sa.Column("risk_type", sa.String(100), nullable=False),
            sa.Column("severity", sa.String(20), nullable=False),
            sa.Column("status", sa.String(30), nullable=False),
            sa.Column("explanation", sa.Text(), nullable=False),
            sa.Column("score", sa.Float(), nullable=False),
            sa.Column("evidence_ids", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
        _indexes("risk_findings", ("tenant_id", "case_id", "rule_run_id", "run_group_id", "risk_type", "severity", "status"))


def downgrade() -> None:
    for table in ("risk_findings", "rule_runs", "document_links"):
        if table in _tables():
            op.drop_table(table)
