"""receipt_shares: optionales Label-Feld

Revision ID: 0021
Revises: 0020
Create Date: 2026-07-23

Nutzerwunsch aus dem Real-World-Test des Beleg-Teilen-Features (siehe
`0020_receipt_shares.py` für den vollen Kontext der Tabelle): sobald ein Link nicht mehr
aktiv ist (verbraucht/abgelaufen/widerrufen), soll er trotzdem in einer persistenten
Historie auffindbar bleiben. Ein frei vergebenes Label (z.B. "Für Versicherung XY") hilft
dabei, einen einzelnen Link in dieser Historie wiederzuerkennen, ohne sich auf Zeitstempel
oder Token-Fragmente verlassen zu müssen.

`nullable=True` ohne `server_default`: anders als in `0017` (dort `NOT NULL` mit
konstantem `server_default`, um einen Table-Rewrite zu vermeiden) ist hier NULL selbst
schon der korrekte "kein Label vergeben"-Zustand für Bestandszeilen — kein Platzhalter,
der später zurückbefüllt werden müsste. Reine Metadaten-Änderung ohne Table-Rewrite.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0021"
down_revision: Union[str, None] = "0020"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "receipt_shares",
        sa.Column("label", sa.String(length=100), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("receipt_shares", "label")
