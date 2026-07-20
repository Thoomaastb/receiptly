"""receipts: Demo-Belege löschen + is_demo-Spalte entfernen (v1.0.0-Cutover)

Revision ID: 0010
Revises: 0009
Create Date: 2026-07-20

Demo-Belege (is_demo=true) wurden bislang bei /auth/register automatisch angelegt
(app/api/auth.py) sowie einmalig per Backfill in Migration 0004 für bereits bestehende
Haushalte nachgezogen. Beides fällt mit dieser Migration weg — siehe begleitender Commit,
der die Erzeugung in auth.py entfernt.

Keine Storage-Datei-Bereinigung nötig: alle Demo-Belege verweisen bewusst auf den
statischen, nie real existierenden Platzhalterpfad "demo/dummy-beleg.jpg" (siehe 0004),
NICHT auf echte Dateien unter storage/originals bzw. storage/thumbs (die werden nur beim
tatsächlichen Datei-Upload in app/services/storage.py geschrieben). Das Löschen dieser
Zeilen hinterlässt daher keine verwaisten Dateien auf der Platte.

Downgrade stellt nur die Spalte wieder her (nullable=False, server_default=false) — die
gelöschten Demo-Zeilen selbst sind nicht rekonstruierbar, das ist bei einem destruktiven
DELETE inhärent und hier bewusst in Kauf genommen (Wegwerf-Testdaten, siehe Docstring).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(sa.text("DELETE FROM receipts WHERE is_demo = true"))
    op.drop_column("receipts", "is_demo")


def downgrade() -> None:
    op.add_column(
        "receipts",
        sa.Column("is_demo", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
