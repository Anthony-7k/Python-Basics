"""human field correction and risk resolution"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "20260928_0004"
down_revision = "20260928_0003"
branch_labels = None
depends_on = None


def _tables() -> set[str]:
    return set(inspect(op.get_bind()).get_table_names())


def _columns(table: str) -> set[str]:
    return {column["name"] for column in inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    field_columns = _columns("field_values")
    if "version" not in field_columns:
        op.add_column(
            "field_values",
            sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        )
    if "source" not in field_columns:
        op.add_column(
            "field_values",
            sa.Column("source", sa.String(30), nullable=False, server_default="EXTRACTED"),
        )

    risk_columns = _columns("risk_findings")
    if "version" not in risk_columns:
        op.add_column(
            "risk_findings",
            sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        )
    if "resolution_reason" not in risk_columns:
        op.add_column("risk_findings", sa.Column("resolution_reason", sa.Text(), nullable=True))
    if "resolved_by" not in risk_columns:
        op.add_column(
            "risk_findings",
            sa.Column("resolved_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        )
    if "resolved_at" not in risk_columns:
        op.add_column(
            "risk_findings",
            sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        )

    if "field_corrections" not in _tables():
        op.create_table(
            "field_corrections",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False),
            sa.Column("case_id", sa.String(36), sa.ForeignKey("review_cases.id"), nullable=False),
            sa.Column("field_value_id", sa.String(36), sa.ForeignKey("field_values.id"), nullable=False),
            sa.Column("actor_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("from_version", sa.Integer(), nullable=False),
            sa.Column("to_version", sa.Integer(), nullable=False),
            sa.Column("previous_value", sa.Text(), nullable=False),
            sa.Column("corrected_value", sa.Text(), nullable=False),
            sa.Column("reason", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
        for column in ("tenant_id", "case_id", "field_value_id", "actor_id"):
            op.create_index(f"ix_field_corrections_{column}", "field_corrections", [column])


def downgrade() -> None:
    if "field_corrections" in _tables():
        op.drop_table("field_corrections")
    for column in ("resolved_at", "resolved_by", "resolution_reason", "version"):
        if column in _columns("risk_findings"):
            op.drop_column("risk_findings", column)
    for column in ("source", "version"):
        if column in _columns("field_values"):
            op.drop_column("field_values", column)
