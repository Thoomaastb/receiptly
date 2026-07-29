"""receipts: Versandkosten/Rabatt/separat ausgewiesene Steuer als eigene Spalten

Revision ID: 0011
Revises: 0010
Create Date: 2026-07-20

Die KI-Struktur-Extraktion füllt items[], aber ursprünglich keine Anpassungszeilen wie
Versandkosten, Gutscheine/Rabatte oder separat ausgewiesene Steuer. Item.total_price
verlangt >= 0 (Field(ge=0)), ein Gutschein als negativer Pseudo-Artikel wäre also
ungültig — daher dedizierte, nullable Felder auf Receipt statt Pseudo-Artikel. NULL heißt
"nicht erfasst", nicht "0". Typisierung (Numeric(10, 2)) analog zu Receipt.total_amount.

tax_amount ist ausdrücklich die *separat ausgewiesene* Steuer für Belege, bei denen sie
nicht bereits in total_amount enthalten ist — total_amount bleibt der Brutto-/
Gesamtbetrag. Verdrahtung (KI-Extraktion, Schema/API, Abgleichslogik im Frontend) folgt
in einer späteren Migration/Änderung, nicht Teil dieser reinen Spalten-Migration.

Reine additive Schema-Änderung (nullable ADD COLUMN) — kein Backfill, kein Lock-Risiko.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: Union[str, None] = "0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("receipts", sa.Column("shipping_cost", sa.Numeric(10, 2), nullable=True))
    op.add_column("receipts", sa.Column("discount_amount", sa.Numeric(10, 2), nullable=True))
    op.add_column("receipts", sa.Column("tax_amount", sa.Numeric(10, 2), nullable=True))


def downgrade() -> None:
    op.drop_column("receipts", "tax_amount")
    op.drop_column("receipts", "discount_amount")
    op.drop_column("receipts", "shipping_cost")
