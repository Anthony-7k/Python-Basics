"""case approvals and immutable generated reports"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "20260928_0006"
down_revision = "20260928_0005"
branch_labels = None
depends_on = None


def _tables() -> set[str]:
    return set(inspect(op.get_bind()).get_table_names())


def _indexes(table: str, columns: tuple[str, ...]) -> None:
    for column in columns:
        op.create_index(f"ix_{table}_{column}", table, [column])


def upgrade() -> None:
    tables = _tables()
    if "approvals" not in tables:
        op.create_table(
            "approvals",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False),
            sa.Column("case_id", sa.String(36), sa.ForeignKey("review_cases.id"), nullable=False),
            sa.Column("decision", sa.String(30), nullable=False),
            sa.Column("reason", sa.Text(), nullable=False),
            sa.Column("actor_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("case_version", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("tenant_id", "case_id", "case_version", name="uq_case_approval_version"),
        )
        _indexes("approvals", ("tenant_id", "case_id", "actor_id"))
    if "reports" not in tables:
        op.create_table(
            "reports",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False),
            sa.Column("case_id", sa.String(36), sa.ForeignKey("review_cases.id"), nullable=False),
            sa.Column("case_version", sa.Integer(), nullable=False),
            sa.Column("report_version", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(30), nullable=False),
            sa.Column("idempotency_key", sa.String(200), nullable=False),
            sa.Column("request_hash", sa.String(64), nullable=False),
            sa.Column("trace_id", sa.String(36), nullable=False),
            sa.Column("object_key", sa.String(500), nullable=True, unique=True),
            sa.Column("content_hash", sa.String(64), nullable=True),
            sa.Column("content_type", sa.String(100), nullable=False),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("generated_at", sa.DateTime(timezone=True), nullable=True),
            sa.UniqueConstraint("tenant_id", "idempotency_key", name="uq_report_idempotency"),
            sa.UniqueConstraint("tenant_id", "case_id", "case_version", name="uq_case_report_version"),
        )
        _indexes("reports", ("tenant_id", "case_id", "status", "trace_id"))


def downgrade() -> None:
    for table in ("reports", "approvals"):
        if table in _tables():
            op.drop_table(table)
