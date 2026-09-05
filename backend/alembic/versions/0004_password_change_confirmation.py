"""users: pending password change requires email confirmation

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-05

"""

from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("pending_password_hash", sa.String(255), nullable=True))
    op.add_column("users", sa.Column("password_change_token", sa.String(64), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "password_change_token")
    op.drop_column("users", "pending_password_hash")
