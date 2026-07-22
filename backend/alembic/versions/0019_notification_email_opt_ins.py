"""users: notification_email_opt_ins-Spalte

Revision ID: 0019
Revises: 0018
Create Date: 2026-07-22

Teil des Benachrichtigungssystem-Plans (siehe `0018_notifications.py` für die
zugehörige `notifications`-Tabelle). Speichert pro User die Liste der `type`-Werte
(siehe `app/models/notification.py::Notification.type`), für die zusätzlich zur
In-App-Benachrichtigung eine E-Mail zugestellt werden soll — Opt-in pro Typ, Default
leer (= konservativ, kein Typ standardmäßig per E-Mail, Konzept Q5).

Eigene Migration statt Bündelung in 0018: sie ändert eine andere, bereits bestehende
Tabelle (`users`) statt die neue `notifications`-Tabelle anzulegen — entspricht der im
Projekt bereits etablierten Konvention, unterschiedliche Anliegen in getrennte
Revisionen zu fassen (vgl. `0016_webauthn_credentials.py` neue Tabelle vs.
`0017_passkey_exclusive_login.py` Spalten-Add auf einer bestehenden Tabelle).

`server_default=sa.text("'[]'::jsonb")` statt Backfill in Python: reine
Metadaten-Änderung im Postgres-Katalog, kein Table-Rewrite auf einer bereits befüllten
`users`-Tabelle, da der Default-Wert konstant ist (gleiche Begründung wie in
`0017_passkey_exclusive_login.py` für `passkey_exclusive_login`).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0019"
down_revision: Union[str, None] = "0018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "notification_email_opt_ins",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "notification_email_opt_ins")
