"""add email confirmation fields to users

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-04

"""

from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("is_email_confirmed", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("users", sa.Column("email_confirmation_token", sa.String(64)))


def downgrade() -> None:
    op.drop_column("users", "email_confirmation_token")
    op.drop_column("users", "is_email_confirmed")
