"""receipts: is_demo flag + backfill demo receipt for existing households

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-07

"""
import uuid
from datetime import date, timedelta
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "receipts",
        sa.Column("is_demo", sa.Boolean(), nullable=False, server_default=sa.false()),
    )

    # Daten-Migration: für jeden bereits existierenden Household-Bucket einen Demo-Beleg
    # anlegen, damit Mosaik/Detail/Stats sofort etwas zum Testen zeigen. Betrifft nur
    # Installationen, die schon vor dieser Migration einen Haushalt hatten — bei frischen
    # Installationen übernimmt das der register()-Endpoint (siehe app/api/auth.py).
    connection = op.get_bind()
    household_buckets = connection.execute(
        sa.text(
            "SELECT b.id AS bucket_id, b.owner_id AS owner_id "
            "FROM buckets b WHERE b.is_default = true"
        )
    ).fetchall()

    for row in household_buckets:
        connection.execute(
            sa.text(
                "INSERT INTO receipts "
                "(id, user_id, bucket_id, receipt_date, total_amount, currency, "
                " file_path, content_hash, status, is_demo, created_at, updated_at) "
                "VALUES "
                "(:id, :user_id, :bucket_id, :receipt_date, :total_amount, 'EUR', "
                " 'demo/dummy-beleg.jpg', :content_hash, 'processed', true, now(), now())"
            ),
            {
                "id": str(uuid.uuid4()),
                "user_id": str(row.owner_id),
                "bucket_id": str(row.bucket_id),
                "receipt_date": (date.today() - timedelta(days=3)).isoformat(),
                "total_amount": 24.99,
                "content_hash": f"demo-{uuid.uuid4().hex[:16]}",
            },
        )


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM receipts WHERE is_demo = true"))
    op.drop_column("receipts", "is_demo")
