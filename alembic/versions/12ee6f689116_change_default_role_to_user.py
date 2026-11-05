"""change default role to USER

Revision ID: 12ee6f689116
Revises: 83f96cff2441
Create Date: 2026-11-04 13:18:13.167396
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = '12ee6f689116'
down_revision: str | None = '83f96cff2441'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        'users', 'role',
        existing_type=sa.String(length=50), existing_nullable=False, server_default='USER',
    )
    op.execute("UPDATE users SET role = 'USER' WHERE role = 'customer'")


def downgrade() -> None:
    op.alter_column(
        'users', 'role',
        existing_type=sa.String(length=50), existing_nullable=False, server_default='customer',
    )
    op.execute("UPDATE users SET role = 'customer' WHERE role = 'USER'")
