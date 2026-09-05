"""maps: sharing polygons between users (viewer/editor roles)

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-05

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

_ROLE_VALUES = ("viewer", "editor")
_map_role = postgresql.ENUM(*_ROLE_VALUES, name="map_role")


def upgrade() -> None:
    _map_role.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "maps",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "map_members",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("map_id", sa.Integer(), sa.ForeignKey("maps.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("invited_email", sa.String(255), nullable=False),
        sa.Column("role", postgresql.ENUM(*_ROLE_VALUES, name="map_role", create_type=False), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("map_id", "user_id", name="uq_map_member"),
    )

    op.add_column("polygons", sa.Column("map_id", sa.Integer(), sa.ForeignKey("maps.id", ondelete="SET NULL")))

    # Данные: у каждого владельца существующих "своих" (is_custom=true)
    # полигонов заводим персональную карту и переносим его полигоны туда —
    # иначе после миграции они выпали бы из любой карты и стали бы
    # невидимы через ?map_id=. Открытые сидовые полигоны датасета
    # (owner_id IS NULL) карты не получают — остаются публичными, как и
    # раньше (см. app/api/routes/polygons.py: map_id IS NULL == открытый).
    conn = op.get_bind()
    owners = conn.execute(
        sa.text("SELECT DISTINCT owner_id FROM polygons WHERE owner_id IS NOT NULL")
    ).scalars().all()
    for owner_id in owners:
        new_map_id = conn.execute(
            sa.text(
                "INSERT INTO maps (name, owner_id, created_at) "
                "VALUES ('Личная карта', :owner_id, now()) RETURNING id"
            ),
            {"owner_id": owner_id},
        ).scalar_one()
        conn.execute(
            sa.text("UPDATE polygons SET map_id = :map_id WHERE owner_id = :owner_id"),
            {"map_id": new_map_id, "owner_id": owner_id},
        )


def downgrade() -> None:
    op.drop_column("polygons", "map_id")
    op.drop_table("map_members")
    op.drop_table("maps")
    _map_role.drop(op.get_bind(), checkfirst=True)
