"""car_info_cache and diag_trim_mapping for plate lookup

Revision ID: f1a2b3c4d5e6
Revises: e8f1a2b3c4d5
Create Date: 2026-10-28 22:55:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "f1a2b3c4d5e6"
down_revision = "e8f1a2b3c4d5"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "car_info_cache",
        sa.Column("car_no", sa.String(length=32), primary_key=True),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("source", sa.String(length=32)),
        sa.Column("fetched_at", sa.DateTime()),
    )
    op.create_table(
        "diag_trim_mapping",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("level", sa.String(length=16), nullable=False),
        sa.Column("diag_idx", sa.String(length=64), nullable=False),
        sa.Column("diag_name", sa.String(length=256)),
        sa.Column("market_name", sa.String(length=256), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="candidate"),
        sa.Column("match_score", sa.Float()),
        sa.Column("source", sa.String(length=16), nullable=False, server_default="auto"),
        sa.Column("parent_market_name", sa.String(length=256)),
        sa.Column("updated_at", sa.DateTime()),
        sa.UniqueConstraint("level", "diag_idx", name="uq_diag_trim_level_idx"),
    )
    op.create_index("ix_diag_trim_mapping_level", "diag_trim_mapping", ["level"])
    op.create_index("ix_diag_trim_mapping_status", "diag_trim_mapping", ["status"])


def downgrade():
    op.drop_index("ix_diag_trim_mapping_status", table_name="diag_trim_mapping")
    op.drop_index("ix_diag_trim_mapping_level", table_name="diag_trim_mapping")
    op.drop_table("diag_trim_mapping")
    op.drop_table("car_info_cache")
