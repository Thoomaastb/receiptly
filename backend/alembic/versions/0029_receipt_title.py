"""receipts: sprechender Beleg-Titel (title/ai_suggested_title)

Revision ID: 0029
Revises: 0028
Create Date: 2026-08-02

Ergänzt `title` und `ai_suggested_title` auf `receipts` (siehe
concepts/beleg-titel.md). Anders als `category` (die am Merchant hängt) gehört der Titel
pro Beleg direkt auf `Receipt`. Herkunfts-Tracking exakt nach dem bestehenden
`ai_suggested_merchant_name`-Muster (Migration 0007): `ai_suggested_title is not None` →
`title` ist ein unbestätigter Vorschlag (KI-Schema-Feld oder Regel-Fallback), darf
automatisch überschrieben werden; `ai_suggested_title is None` → vom Nutzer bestätigt,
wird nie mehr automatisch überschrieben. Verwerfen läuft über das bestehende
`dismiss_ai_suggestion`-Verhalten mit (kein eigenes Dismiss-Flag), Verdrahtung folgt in
einer späteren Änderung (KI-Extraktions-Schema, API, Fallback-Template), nicht Teil
dieser reinen Spalten-Migration.

Rein additive Migration, kein Backfill: beide Spalten starten NULL für bestehende
Belege — ein einmaliger nachträglicher Backfill für Bestandsbelege ist als separater,
späterer Schritt vorgesehen (Business-Logik mit KI-Call, nicht Teil dieser Migration).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0029"
down_revision: Union[str, None] = "0028"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("receipts", sa.Column("title", sa.String(255), nullable=True))
    op.add_column("receipts", sa.Column("ai_suggested_title", sa.String(255), nullable=True))


def downgrade() -> None:
    op.drop_column("receipts", "ai_suggested_title")
    op.drop_column("receipts", "title")
