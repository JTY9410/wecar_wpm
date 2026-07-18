"""hierarchy_signup_wholesale

Revision ID: a1b2c3d4e5f6
Revises: 5728eb86808e
Create Date: 2026-07-18 09:40:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "a1b2c3d4e5f6"
down_revision = "5728eb86808e"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "vehicle_maker",
        sa.Column("maker_no", sa.String(length=32), nullable=False),
        sa.Column("maker_name", sa.String(length=128), nullable=False),
        sa.Column("sort_no", sa.Integer(), nullable=True),
        sa.Column("synced_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("maker_no"),
    )
    with op.batch_alter_table("vehicle_maker", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_vehicle_maker_maker_name"), ["maker_name"], unique=False)

    op.create_table(
        "vehicle_model",
        sa.Column("model_no", sa.String(length=32), nullable=False),
        sa.Column("maker_no", sa.String(length=32), nullable=True),
        sa.Column("model_name", sa.String(length=128), nullable=False),
        sa.Column("sort_no", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["maker_no"], ["vehicle_maker.maker_no"]),
        sa.PrimaryKeyConstraint("model_no"),
    )
    with op.batch_alter_table("vehicle_model", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_vehicle_model_maker_no"), ["maker_no"], unique=False)

    op.create_table(
        "vehicle_model_detail",
        sa.Column("mdetail_no", sa.String(length=32), nullable=False),
        sa.Column("model_no", sa.String(length=32), nullable=True),
        sa.Column("mdetail_name", sa.String(length=256), nullable=False),
        sa.Column("sort_no", sa.Integer(), nullable=True),
        sa.Column("st_year", sa.Integer(), nullable=True),
        sa.Column("ed_year", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["model_no"], ["vehicle_model.model_no"]),
        sa.PrimaryKeyConstraint("mdetail_no"),
    )
    with op.batch_alter_table("vehicle_model_detail", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_vehicle_model_detail_model_no"), ["model_no"], unique=False)

    op.create_table(
        "vehicle_grade",
        sa.Column("grade_no", sa.String(length=32), nullable=False),
        sa.Column("mdetail_no", sa.String(length=32), nullable=True),
        sa.Column("grade_name", sa.String(length=128), nullable=False),
        sa.Column("sort_no", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["mdetail_no"], ["vehicle_model_detail.mdetail_no"]),
        sa.PrimaryKeyConstraint("grade_no"),
    )
    with op.batch_alter_table("vehicle_grade", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_vehicle_grade_mdetail_no"), ["mdetail_no"], unique=False)

    op.create_table(
        "vehicle_grade_detail",
        sa.Column("gdetail_no", sa.String(length=32), nullable=False),
        sa.Column("grade_no", sa.String(length=32), nullable=True),
        sa.Column("gdetail_name", sa.String(length=128), nullable=False),
        sa.Column("sort_no", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["grade_no"], ["vehicle_grade.grade_no"]),
        sa.PrimaryKeyConstraint("gdetail_no"),
    )
    with op.batch_alter_table("vehicle_grade_detail", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_vehicle_grade_detail_grade_no"), ["grade_no"], unique=False)

    with op.batch_alter_table("user", schema=None) as batch_op:
        batch_op.add_column(sa.Column("name", sa.String(length=80), nullable=True))
        batch_op.add_column(sa.Column("phone", sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column("affiliation", sa.String(length=128), nullable=True))
        batch_op.add_column(sa.Column("is_approved", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column("note", sa.Text(), nullable=True))

    with op.batch_alter_table("listing", schema=None) as batch_op:
        batch_op.alter_column("maker_no", existing_type=sa.Integer(), type_=sa.String(length=32), existing_nullable=True)
        batch_op.add_column(sa.Column("model_no", sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column("mdetail_no", sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column("grade_no", sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column("gdetail_no", sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column("car_fuel", sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column("car_awd", sa.String(length=16), nullable=True))
        batch_op.add_column(sa.Column("car_code", sa.String(length=255), nullable=True))
        batch_op.create_index(batch_op.f("ix_listing_car_code"), ["car_code"], unique=False)

    with op.batch_alter_table("auction_record", schema=None) as batch_op:
        batch_op.add_column(sa.Column("mdetail_name", sa.String(length=150), nullable=True))
        batch_op.add_column(sa.Column("grade_name", sa.String(length=128), nullable=True))
        batch_op.add_column(sa.Column("gdetail_name", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("awd", sa.String(length=16), nullable=True))
        batch_op.add_column(sa.Column("maker_no", sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column("model_no", sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column("mdetail_no", sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column("grade_no", sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column("gdetail_no", sa.String(length=32), nullable=True))
        batch_op.alter_column("car_code", existing_type=sa.String(length=64), type_=sa.String(length=255), existing_nullable=True)
        batch_op.create_index(batch_op.f("ix_auction_record_maker_no"), ["maker_no"], unique=False)
        batch_op.create_index(batch_op.f("ix_auction_record_model_no"), ["model_no"], unique=False)
        batch_op.create_index(batch_op.f("ix_auction_record_mdetail_no"), ["mdetail_no"], unique=False)
        batch_op.create_index(batch_op.f("ix_auction_record_grade_no"), ["grade_no"], unique=False)
        batch_op.create_index(batch_op.f("ix_auction_record_gdetail_no"), ["gdetail_no"], unique=False)

    with op.batch_alter_table("market_summary", schema=None) as batch_op:
        batch_op.add_column(sa.Column("mdetail_name", sa.String(length=150), nullable=True))
        batch_op.add_column(sa.Column("grade_name", sa.String(length=128), nullable=True))
        batch_op.add_column(sa.Column("gdetail_name", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("fuel", sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column("awd", sa.String(length=16), nullable=True))
        batch_op.alter_column("car_code", existing_type=sa.String(length=64), type_=sa.String(length=255), existing_nullable=True)
        batch_op.create_index(batch_op.f("ix_market_summary_mdetail_name"), ["mdetail_name"], unique=False)
        batch_op.create_index(batch_op.f("ix_market_summary_grade_name"), ["grade_name"], unique=False)
        batch_op.create_index(batch_op.f("ix_market_summary_gdetail_name"), ["gdetail_name"], unique=False)
        batch_op.create_index(batch_op.f("ix_market_summary_fuel"), ["fuel"], unique=False)
        batch_op.create_index(batch_op.f("ix_market_summary_awd"), ["awd"], unique=False)
        batch_op.create_index(batch_op.f("ix_market_summary_km_bin"), ["km_bin"], unique=False)


def downgrade():
    with op.batch_alter_table("market_summary", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_market_summary_km_bin"))
        batch_op.drop_index(batch_op.f("ix_market_summary_awd"))
        batch_op.drop_index(batch_op.f("ix_market_summary_fuel"))
        batch_op.drop_index(batch_op.f("ix_market_summary_gdetail_name"))
        batch_op.drop_index(batch_op.f("ix_market_summary_grade_name"))
        batch_op.drop_index(batch_op.f("ix_market_summary_mdetail_name"))
        batch_op.drop_column("awd")
        batch_op.drop_column("fuel")
        batch_op.drop_column("gdetail_name")
        batch_op.drop_column("grade_name")
        batch_op.drop_column("mdetail_name")
        batch_op.alter_column("car_code", existing_type=sa.String(length=255), type_=sa.String(length=64), existing_nullable=True)

    with op.batch_alter_table("auction_record", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_auction_record_gdetail_no"))
        batch_op.drop_index(batch_op.f("ix_auction_record_grade_no"))
        batch_op.drop_index(batch_op.f("ix_auction_record_mdetail_no"))
        batch_op.drop_index(batch_op.f("ix_auction_record_model_no"))
        batch_op.drop_index(batch_op.f("ix_auction_record_maker_no"))
        batch_op.drop_column("gdetail_no")
        batch_op.drop_column("grade_no")
        batch_op.drop_column("mdetail_no")
        batch_op.drop_column("model_no")
        batch_op.drop_column("maker_no")
        batch_op.drop_column("awd")
        batch_op.drop_column("gdetail_name")
        batch_op.drop_column("grade_name")
        batch_op.drop_column("mdetail_name")
        batch_op.alter_column("car_code", existing_type=sa.String(length=255), type_=sa.String(length=64), existing_nullable=True)

    with op.batch_alter_table("listing", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_listing_car_code"))
        batch_op.drop_column("car_code")
        batch_op.drop_column("car_awd")
        batch_op.drop_column("car_fuel")
        batch_op.drop_column("gdetail_no")
        batch_op.drop_column("grade_no")
        batch_op.drop_column("mdetail_no")
        batch_op.drop_column("model_no")
        batch_op.alter_column("maker_no", existing_type=sa.String(length=32), type_=sa.Integer(), existing_nullable=True)

    with op.batch_alter_table("user", schema=None) as batch_op:
        batch_op.drop_column("note")
        batch_op.drop_column("is_approved")
        batch_op.drop_column("affiliation")
        batch_op.drop_column("phone")
        batch_op.drop_column("name")

    op.drop_table("vehicle_grade_detail")
    op.drop_table("vehicle_grade")
    op.drop_table("vehicle_model_detail")
    op.drop_table("vehicle_model")
    op.drop_table("vehicle_maker")
