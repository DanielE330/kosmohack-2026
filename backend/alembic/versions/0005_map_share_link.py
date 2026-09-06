"""maps: share-by-link token (открыть расшаренный полигон без входа)

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-06

"""

from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # NULL у всех существующих карт — то есть ни одна карта не становится
    # доступной по ссылке задним числом: токен появляется только после
    # явного POST /polygons/{id}/share-link.
    op.add_column("maps", sa.Column("share_token", sa.String(64), nullable=True))
    op.create_index("ix_maps_share_token", "maps", ["share_token"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_maps_share_token", table_name="maps")
    op.drop_column("maps", "share_token")
