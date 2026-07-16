"""receipts/ai_settings: KI-Struktur-Extraktion — Vorschlagsfelder + Modell-Override

Revision ID: 0007
Revises: 0006
Create Date: 2026-07-15

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "receipts", sa.Column("ai_suggested_merchant_name", sa.String(255), nullable=True)
    )
    op.add_column(
        "receipts", sa.Column("ai_suggested_category", sa.String(100), nullable=True)
    )
    op.add_column(
        "receipts", sa.Column("ai_extraction_note", sa.String(500), nullable=True)
    )
    op.add_column(
        "receipts",
        sa.Column("ai_extracted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column("ai_settings", sa.Column("model_name", sa.String(255), nullable=True))


def downgrade() -> None:
    op.drop_column("ai_settings", "model_name")
    op.drop_column("receipts", "ai_extracted_at")
    op.drop_column("receipts", "ai_extraction_note")
    op.drop_column("receipts", "ai_suggested_category")
    op.drop_column("receipts", "ai_suggested_merchant_name")
