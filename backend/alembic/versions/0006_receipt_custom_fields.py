"""receipts: custom_fields JSONB (kategorie-spezifische Zusatzfelder, z.B. Kilometerstand)

Revision ID: 0006
Revises: 0005
Create Date: 2026-07-15

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("receipts", sa.Column("custom_fields", postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("receipts", "custom_fields")
