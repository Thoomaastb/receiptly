"""receipts: Herkunfts-Tracking für shipping_cost/discount_amount/tax_amount

Revision ID: 0028
Revises: 0027
Create Date: 2026-07-31

Migration 0011 hat shipping_cost/discount_amount/tax_amount bewusst OHNE das bei
receipt_date/total_amount/currency etablierte ai_suggested_X-Herkunfts-Tracking
eingeführt. In der Praxis hat sich das als Bug gezeigt: ein einmal fehlerhaft von der KI
gesetzter Wert (z.B. durch einen inzwischen gefixten Prompt-Bug) blieb dauerhaft stehen,
weil der Re-Analyse-Code nur befüllt, wenn das Feld noch NULL ist — es gab kein Signal,
um "war nur KI-Vermutung, darf überschrieben werden" von "wurde vom Nutzer bestätigt,
darf nicht mehr überschrieben werden" zu unterscheiden.

Diese Migration schließt die Lücke zum bestehenden Muster: ai_suggested_X is not None →
X gilt als unbestätigte KI-Schätzung und darf bei erneuter Analyse überschrieben werden.
ai_suggested_X is None → X gilt als vom Nutzer bestätigt und wird nie mehr automatisch
überschrieben. Typisierung (Numeric(10, 2)) identisch zu den jeweiligen Basis-Feldern.
Verdrahtung (Re-Analyse-Logik, Schema/API) folgt in einer späteren Änderung, nicht Teil
dieser reinen Spalten-Migration.

Reine additive Schema-Änderung (nullable ADD COLUMN) — kein Backfill, kein Lock-Risiko.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0028"
down_revision: Union[str, None] = "0027"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("receipts", sa.Column("ai_suggested_shipping_cost", sa.Numeric(10, 2), nullable=True))
    op.add_column("receipts", sa.Column("ai_suggested_discount_amount", sa.Numeric(10, 2), nullable=True))
    op.add_column("receipts", sa.Column("ai_suggested_tax_amount", sa.Numeric(10, 2), nullable=True))


def downgrade() -> None:
    op.drop_column("receipts", "ai_suggested_tax_amount")
    op.drop_column("receipts", "ai_suggested_discount_amount")
    op.drop_column("receipts", "ai_suggested_shipping_cost")
