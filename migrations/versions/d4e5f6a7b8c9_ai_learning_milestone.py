"""ai_learning_milestone table

Revision ID: d4e5f6a7b8c9
Revises: c7d9e2f1a0b3
Create Date: 2026-08-02 11:20:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "d4e5f6a7b8c9"
down_revision = "c7d9e2f1a0b3"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "ai_learning_milestone" in set(inspector.get_table_names()):
        return
    op.create_table(
        "ai_learning_milestone",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("recorded_date", sa.Date(), nullable=False),
        sa.Column("phase", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("user.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )


def downgrade():
    op.drop_table("ai_learning_milestone")
