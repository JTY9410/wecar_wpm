"""learned glossary + translation_cache hit_count/engine

Revision ID: c7d9e2f1a0b3
Revises: 869244050cd4
Create Date: 2026-08-02 08:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "c7d9e2f1a0b3"
down_revision = "869244050cd4"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "translation_cache" in tables:
        existing = {c["name"] for c in inspector.get_columns("translation_cache")}
        with op.batch_alter_table("translation_cache") as batch_op:
            if "hit_count" not in existing:
                batch_op.add_column(
                    sa.Column("hit_count", sa.Integer(), nullable=False, server_default="1")
                )
            if "engine" not in existing:
                batch_op.add_column(sa.Column("engine", sa.String(length=20), nullable=True))

    if "learned_glossary" not in tables:
        op.create_table(
            "learned_glossary",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("source_hash", sa.String(length=64), nullable=False),
            sa.Column("source_text", sa.Text(), nullable=False),
            sa.Column("lang", sa.String(length=5), nullable=False),
            sa.Column("translated_text", sa.Text(), nullable=False),
            sa.Column("promoted_from", sa.String(length=20)),
            sa.Column("hit_count_at_promote", sa.Integer()),
            sa.Column("created_at", sa.DateTime()),
            sa.Column("updated_at", sa.DateTime()),
            sa.UniqueConstraint("source_hash", "lang", name="uq_learned_glossary"),
        )
        op.create_index("ix_learned_glossary_source_hash", "learned_glossary", ["source_hash"])


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "learned_glossary" in tables:
        op.drop_index("ix_learned_glossary_source_hash", table_name="learned_glossary")
        op.drop_table("learned_glossary")
    if "translation_cache" in tables:
        existing = {c["name"] for c in inspector.get_columns("translation_cache")}
        with op.batch_alter_table("translation_cache") as batch_op:
            if "engine" in existing:
                batch_op.drop_column("engine")
            if "hit_count" in existing:
                batch_op.drop_column("hit_count")
