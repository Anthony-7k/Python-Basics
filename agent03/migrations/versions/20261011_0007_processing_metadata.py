"""Persist OCR/model provenance and measured processing latency."""
import sqlalchemy as sa
from alembic import op

revision = "20261011_0007"
down_revision = "20260928_0006"
branch_labels = None
depends_on = None


def upgrade():
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("extraction_runs")}
    if "processing_metadata" not in columns:
        op.add_column("extraction_runs", sa.Column("processing_metadata", sa.JSON(), nullable=False,
                                                  server_default="{}"))


def downgrade():
    op.drop_column("extraction_runs", "processing_metadata")
