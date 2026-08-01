"""translation cache self-learning fields (reviewed, created_at, updated_at)

Revision ID: 869244050cd4
Revises: a1b2c3d4e5f6
Create Date: 2026-08-01 21:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "869244050cd4"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    existing = {c["name"] for c in sa.inspect(bind).get_columns("translation_cache")}
    with op.batch_alter_table("translation_cache") as batch_op:
        if "reviewed" not in existing:
            batch_op.add_column(
                sa.Column("reviewed", sa.Boolean(), nullable=False, server_default=sa.false())
            )
        if "created_at" not in existing:
            batch_op.add_column(sa.Column("created_at", sa.DateTime(), nullable=True))
        if "updated_at" not in existing:
            batch_op.add_column(sa.Column("updated_at", sa.DateTime(), nullable=True))


def downgrade():
    with op.batch_alter_table("translation_cache") as batch_op:
        batch_op.drop_column("updated_at")
        batch_op.drop_column("created_at")
        batch_op.drop_column("reviewed")
