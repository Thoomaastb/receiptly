"""Kategorie-Neuordnung: receipts.category-Spalte + Backfill aus merchants.category

Revision ID: 0023
Revises: 0022
Create Date: 2026-07-25

Erste DB-Vorbereitung für das Feature "Kategorie-Neuordnung" (siehe
concepts/kategorie-neuordnung.md, Plan-Schritt A1). Kategorie hängt heute strukturell am
Händler (`Merchant.category`) statt am einzelnen Beleg — `Receipt.category` ist bislang
nur eine read-only Property, die `merchant.category` durchreicht. Diese Migration legt
die neue Spalte `receipts.category` bereits an und befüllt sie per Backfill mit dem
aktuellen `merchants.category`-Wert, damit jeder bestehende Beleg beim späteren Umschalten
auf die neue Spalte (Schritt A2/A3) seinen bisherigen effektiven Kategoriewert als
Startwert hat. Backend/App nutzen die neue Spalte in diesem Schritt noch NICHT — reiner
DB-Vorlauf, additiv, kein Table-Rewrite (gleiches Muster wie `0017`/`0021`/`0022`).

Bewusst kein DB-Enum und kein CHECK-Constraint auf die erlaubten Kategoriewerte: die
Whitelist kommt später auf Python-/Pydantic-Ebene, weil die Taxonomie noch wächst und ein
CHECK-Constraint jede künftige Erweiterung an eine Migration koppeln würde.
`merchants.category` bleibt unverändert bestehen (Datenherkunft für den Backfill).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0023"
down_revision: Union[str, None] = "0022"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "receipts",
        sa.Column("category", sa.String(length=100), nullable=True),
    )
    op.create_index("ix_receipts_category", "receipts", ["category"])
    op.execute(
        """
        UPDATE receipts SET category = merchants.category
        FROM merchants
        WHERE receipts.merchant_id = merchants.id AND merchants.category IS NOT NULL
        """
    )


def downgrade() -> None:
    op.drop_index("ix_receipts_category", table_name="receipts")
    op.drop_column("receipts", "category")
