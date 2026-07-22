"""household_security_settings: passkey_exclusive_login-Spalte

Revision ID: 0017
Revises: 0016
Create Date: 2026-07-22

Teil von Phase 4 des Security-Hardening-Plans (Passkey-Exklusiv-Login, siehe
concepts/security-hardening.md Abschnitt 4.1). Warum diese Spalte erst jetzt und nicht
schon in Phase 2 zusammen mit `household_security_settings` angelegt wurde, ist bereits
im Docstring von Migration 0014 sowie im Model-Docstring
(`app/models/household_security_settings.py`) begründet (Lehre aus `users.totp_secret`)
— hier nicht wiederholt.

`NOT NULL DEFAULT false` per `server_default`: reine Metadaten-Änderung in Postgres
(kein Table-Rewrite, kein Backfill nötig), da der Default-Wert konstant ist und ab
PG 11 direkt im Katalog vermerkt wird statt pro Zeile geschrieben zu werden.

Precondition-Gate (alle Haushalts-User brauchen einen Passkey, bevor der Schalter
aktivierbar ist) und die Login-Ablehnung sind bewusst nicht Teil dieser Migration —
reine Anwendungslogik, folgt separat im Backend.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0017"
down_revision: Union[str, None] = "0016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "household_security_settings",
        sa.Column(
            "passkey_exclusive_login",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("household_security_settings", "passkey_exclusive_login")
