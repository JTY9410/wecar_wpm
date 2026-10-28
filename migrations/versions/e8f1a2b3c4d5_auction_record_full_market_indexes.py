"""auction_record indexes for full-market week-range queries

Revision ID: e8f1a2b3c4d5
Revises: 508eee195e17
Create Date: 2026-10-28 22:40:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "e8f1a2b3c4d5"
down_revision = "508eee195e17"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "auction_record" not in set(inspector.get_table_names()):
        return
    existing = {ix["name"] for ix in inspector.get_indexes("auction_record")}
    if "ix_auction_record_week_trim" not in existing:
        op.create_index(
            "ix_auction_record_week_trim",
            "auction_record",
            ["week_no", "maker", "model_name", "gdetail_name"],
        )
    if "ix_auction_record_km_acc" not in existing:
        op.create_index(
            "ix_auction_record_km_acc",
            "auction_record",
            ["km_bin", "is_accident_free"],
        )


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "auction_record" not in set(inspector.get_table_names()):
        return
    existing = {ix["name"] for ix in inspector.get_indexes("auction_record")}
    if "ix_auction_record_km_acc" in existing:
        op.drop_index("ix_auction_record_km_acc", table_name="auction_record")
    if "ix_auction_record_week_trim" in existing:
        op.drop_index("ix_auction_record_week_trim", table_name="auction_record")
