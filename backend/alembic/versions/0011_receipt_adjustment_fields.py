"""receipts: Versandkosten/Rabatt/separat ausgewiesene Steuer als eigene Spalten

Revision ID: 0011
Revises: 0010
Create Date: 2026-07-20

Hintergrund: Die KI-Struktur-Extraktion füllt bislang nur items[], aber keine
Anpassungszeilen wie Versandkosten, Gutscheine/Rabatte oder separat ausgewiesene Steuer.
Item.total_price verlangt >= 0 (siehe app/schemas/receipt.py, Field(ge=0)), ein Gutschein
als negativer Pseudo-Artikel wäre also ungültig — daher dedizierte, nullable Felder auf
Receipt statt Pseudo-Artikel. Alle drei Spalten bewusst nullable (kein Default/Backfill
nötig): sie beschreiben "diese Anpassung ist bekannt/erfasst", NULL heißt "nicht erfasst",
nicht "0". Typisierung (Numeric(10, 2)) analog zu Receipt.total_amount.

tax_amount ist ausdrücklich die *separat ausgewiesene* Steuer für Belege, bei denen sie
nicht bereits in total_amount enthalten ist (z.B. wenn ein Händler Netto- und Steuerbetrag
getrennt ausweist) — total_amount bleibt weiterhin der Brutto-/Gesamtbetrag. Die Logik, wie
tax_amount beim Abgleich (items vs. total_amount) berücksichtigt wird, ist bewusst nicht
Teil dieser Migration (siehe Scope-Grenze im Auftrag) und folgt separat in
Backend-Abgleichslogik/Pydantic-Schemas/Frontend-Banner.

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
