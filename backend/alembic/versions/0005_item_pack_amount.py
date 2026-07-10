"""items: pack_amount + pack_unit (Menge pro Einheit, getrennt von Anzahl/quantity)

Revision ID: 0005
Revises: 0004
Create Date: 2026-07-10

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("items", sa.Column("pack_amount", sa.Numeric(10, 3), nullable=True))
    op.add_column("items", sa.Column("pack_unit", sa.String(20), nullable=True))


def downgrade() -> None:
    op.drop_column("items", "pack_unit")
    op.drop_column("items", "pack_amount")
