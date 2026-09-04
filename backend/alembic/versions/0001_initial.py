"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-09-04

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

_STATUS_VALUES = ("normal", "suppression", "critical")
_ndvi_status = postgresql.ENUM(*_STATUS_VALUES, name="ndvi_status")


def upgrade() -> None:
    _ndvi_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255)),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "polygons",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("label", sa.String(255)),
        sa.Column("crop_type", sa.String(255)),
        sa.Column("area_id", sa.String(64)),
        sa.Column("points", postgresql.JSONB(), nullable=False),
        sa.Column("is_custom", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "ndvi_observations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("polygon_id", sa.String(64), sa.ForeignKey("polygons.id", ondelete="CASCADE"), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("s2_ndvi", sa.Float()),
        sa.Column("s2_evi", sa.Float()),
        sa.Column("s2_ndwi", sa.Float()),
        sa.Column("landsat_ndvi", sa.Float()),
        sa.Column("landsat_evi", sa.Float()),
        sa.Column("landsat_ndwi", sa.Float()),
        sa.Column("modis_ndvi", sa.Float()),
        sa.Column("modis_evi", sa.Float()),
        sa.Column("era5_temp_c", sa.Float()),
        sa.Column("era5_precip_mm", sa.Float()),
        sa.Column("doy", sa.Integer()),
        sa.Column("primary_ndvi", sa.Float()),
        sa.Column("primary_ndvi_pred", sa.Float()),
        sa.Column("is_synthetic_gap", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("ndvi_climatology_mean", sa.Float()),
        sa.Column("ndvi_climatology_std", sa.Float()),
        sa.Column("ndvi_zscore", sa.Float()),
        sa.Column("n_reference_years", sa.Integer()),
        sa.Column("status", postgresql.ENUM(*_STATUS_VALUES, name="ndvi_status", create_type=False)),
        sa.Column("crop_type", sa.String(255)),
        sa.UniqueConstraint("polygon_id", "date", name="uq_polygon_date"),
    )
    op.create_index("ix_ndvi_observations_polygon_id", "ndvi_observations", ["polygon_id"])

    op.create_table(
        "anomaly_periods",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("polygon_id", sa.String(64), sa.ForeignKey("polygons.id", ondelete="CASCADE"), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column(
            "severity", postgresql.ENUM(*_STATUS_VALUES, name="ndvi_status", create_type=False), nullable=False
        ),
        sa.Column("min_z_score", sa.Float(), nullable=False),
        sa.Column("deviation", sa.Float(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False, server_default=""),
    )
    op.create_index("ix_anomaly_periods_polygon_id", "anomaly_periods", ["polygon_id"])


def downgrade() -> None:
    op.drop_table("anomaly_periods")
    op.drop_table("ndvi_observations")
    op.drop_table("polygons")
    op.drop_table("users")
    _ndvi_status.drop(op.get_bind(), checkfirst=True)
