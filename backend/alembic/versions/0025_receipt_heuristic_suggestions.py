"""receipts: Vorschlagsfelder für Datum/Betrag/Währung (lokale Heuristik-Vorbefüllung)

Revision ID: 0025
Revises: 0024
Create Date: 2026-07-27

Ergänzt `ai_suggested_receipt_date`, `ai_suggested_total_amount` und
`ai_suggested_currency` auf `receipts` — analog zu den bestehenden
`ai_suggested_merchant_name`/`ai_suggested_category` aus Migration 0007. Zweck: eine
neue clientseitige Heuristik (Regex auf OCR-Text, siehe concepts/lokale-heuristik-
vorbefuellung.md, Plan-Schritt A3) UND ein Bugfix in der bestehenden KI-Extraktion
(Plan-Schritt A2) brauchen für `receipt_date`/`total_amount`/`currency` ein
Herkunfts-Tracking, das bislang nur für Händlername/Kategorie existierte — die Frage
"ist dieser Wert noch eine unbestätigte Schätzung oder schon vom Nutzer bestätigt?".

Sonderfall `currency`: `receipts.currency` ist selbst `NOT NULL DEFAULT 'EUR'` und kann
"nie gesetzt" daher — anders als `receipt_date`/`total_amount` — nicht über `NULL` auf
der Hauptspalte abbilden. `ai_suggested_currency` wird dadurch (in der späteren
Anwendungslogik, nicht Teil dieser Migration) die einzige Quelle der Wahrheit dafür, ob
der aktuelle `currency`-Wert noch eine unbestätigte Schätzung ist oder vom Nutzer
bestätigt wurde.

Rein additive Migration, kein Backfill nötig: alle drei Spalten starten NULL für
bestehende Belege — das ist korrekt, da "kein bekannter Schätzwert" für Alt-Belege der
richtige Ausgangszustand ist. Modell-/Schema-/API-Wiring folgt in A2/A2b.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0025"
down_revision: Union[str, None] = "0024"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "receipts", sa.Column("ai_suggested_receipt_date", sa.Date(), nullable=True)
    )
    op.add_column(
        "receipts",
        sa.Column("ai_suggested_total_amount", sa.Numeric(10, 2), nullable=True),
    )
    op.add_column(
        "receipts", sa.Column("ai_suggested_currency", sa.String(3), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("receipts", "ai_suggested_currency")
    op.drop_column("receipts", "ai_suggested_total_amount")
    op.drop_column("receipts", "ai_suggested_receipt_date")
