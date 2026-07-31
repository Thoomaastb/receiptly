"""items: Rabatt-Unterzeile pro Artikel als eigene Spalte

Revision ID: 0027
Revises: 0026
Create Date: 2026-07-31

Analog zu Migration 0011 (Receipt.shipping_cost/discount_amount/tax_amount): die
KI-Struktur-Extraktion verwarf bislang Rabatt-Zeilen unter einem Artikel auf dem Kassenbon,
weil Item.total_price >= 0 verlangt (Field(ge=0)) und ein Rabatt als negativer
Pseudo-Artikel damit ungültig wäre. Item.total_price bleibt der Netto-/Endpreis des
Artikels nach Rabatt; discount_amount ist der zugehörige, separat ausgewiesene
Rabattbetrag. NULL heißt "kein Rabatt erfasst", nicht "0". Der Bruttopreis vor Rabatt ist
bei Bedarf über total_price + discount_amount rekonstruierbar. Typisierung
(Numeric(10, 2)) analog zu Receipt.discount_amount. Verdrahtung (KI-Extraktion,
Schema/API, Frontend) folgt in einer späteren Änderung, nicht Teil dieser reinen
Spalten-Migration.

Reine additive Schema-Änderung (nullable ADD COLUMN) — kein Backfill, kein Lock-Risiko.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0027"
down_revision: Union[str, None] = "0026"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("items", sa.Column("discount_amount", sa.Numeric(10, 2), nullable=True))


def downgrade() -> None:
    op.drop_column("items", "discount_amount")
