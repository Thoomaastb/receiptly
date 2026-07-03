"""receipts: receipt_date and total_amount nullable (unknown at upload time, before OCR/AI)

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-03

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("receipts", "receipt_date", nullable=True)
    op.alter_column("receipts", "total_amount", nullable=True)


def downgrade() -> None:
    op.alter_column("receipts", "total_amount", nullable=False)
    op.alter_column("receipts", "receipt_date", nullable=False)
