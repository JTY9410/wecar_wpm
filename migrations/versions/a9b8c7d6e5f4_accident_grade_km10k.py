"""accident_grade columns + note km bin 10k reclassify

Revision ID: a9b8c7d6e5f4
Revises: f1a2b3c4d5e6
Create Date: 2026-10-30 12:10:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "a9b8c7d6e5f4"
down_revision = "f1a2b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "auction_record" in tables:
        cols = {c["name"] for c in inspector.get_columns("auction_record")}
        if "accident_grade" not in cols:
            with op.batch_alter_table("auction_record") as batch:
                batch.add_column(sa.Column("accident_grade", sa.String(length=40)))
            op.create_index(
                "ix_auction_record_accident_grade",
                "auction_record",
                ["accident_grade"],
            )

    if "market_summary" in tables:
        cols = {c["name"] for c in inspector.get_columns("market_summary")}
        if "accident_grade" not in cols:
            with op.batch_alter_table("market_summary") as batch:
                batch.add_column(sa.Column("accident_grade", sa.String(length=40)))
            op.create_index(
                "ix_market_summary_accident_grade",
                "market_summary",
                ["accident_grade"],
            )

    # analysis_logic mileage.km_bin step → 10000 when row exists
    if "analysis_logic" in tables:
        rows = bind.execute(
            sa.text("SELECT id, params FROM analysis_logic WHERE code = 'mileage.km_bin'")
        ).fetchall()
        for row_id, params in rows:
            # params may be JSON text or already dict depending on dialect
            import json
            if params is None:
                new_params = {"step": 10000, "max": 200000}
            elif isinstance(params, dict):
                new_params = dict(params)
                new_params["step"] = 10000
                new_params.setdefault("max", 200000)
            else:
                try:
                    new_params = json.loads(params) if params else {}
                except Exception:
                    new_params = {}
                new_params["step"] = 10000
                new_params.setdefault("max", 200000)
            bind.execute(
                sa.text("UPDATE analysis_logic SET params = :p WHERE id = :id"),
                {"p": json.dumps(new_params, ensure_ascii=False), "id": row_id},
            )


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "market_summary" in tables:
        cols = {c["name"] for c in inspector.get_columns("market_summary")}
        if "accident_grade" in cols:
            op.drop_index("ix_market_summary_accident_grade", table_name="market_summary")
            with op.batch_alter_table("market_summary") as batch:
                batch.drop_column("accident_grade")
    if "auction_record" in tables:
        cols = {c["name"] for c in inspector.get_columns("auction_record")}
        if "accident_grade" in cols:
            op.drop_index("ix_auction_record_accident_grade", table_name="auction_record")
            with op.batch_alter_table("auction_record") as batch:
                batch.drop_column("accident_grade")
