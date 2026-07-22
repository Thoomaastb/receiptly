"""smtp_settings: instanzweite SMTP-Konfiguration für ausgehenden Mail-Versand

Revision ID: 0015
Revises: 0014
Create Date: 2026-07-21

Im Unterschied zu ai_settings (Migration 0003, haushaltsweit — ein Haushalt hat eigene
KI-Einstellungen) ist SMTP ein Instanz-, kein Haushalts-Konzept: es gibt nur einen
ausgehenden Mail-Versand für die gesamte Anwendung. Die Tabelle ist daher ein echtes
Singleton statt einer Zuordnung über einen Fremdschlüssel: `id` ist per DEFAULT fix auf
1 gesetzt und per CHECK-Constraint auf genau diesen Wert beschränkt, was eine zweite
Zeile strukturell verhindert (nicht nur per Anwendungslogik/Unique-Constraint auf einer
Konstante, die theoretisch umgangen werden könnte). Ergänzt/löst perspektivisch die
bisher rein .env-basierte SMTP-Konfiguration in app/config.py (smtp_host etc., genutzt
von app/services/email.py) ab — die Anbindung in Service/API folgt in einem separaten
Schritt.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0015"
down_revision: Union[str, None] = "0014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "smtp_settings",
        sa.Column("id", sa.SmallInteger(), server_default="1", nullable=False),
        sa.Column("host", sa.String(length=255), nullable=True),
        sa.Column("port", sa.Integer(), server_default="587", nullable=False),
        sa.Column("username", sa.String(length=255), nullable=True),
        sa.Column("encrypted_password", sa.String(length=1024), nullable=True),
        sa.Column("from_email", sa.String(length=255), nullable=True),
        sa.Column(
            "encryption", sa.String(length=16), server_default="starttls", nullable=False
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name="pk_smtp_settings"),
        # Namen bewusst nur der semantische Suffix, nicht der voll qualifizierte Name —
        # op.create_table() übernimmt die naming_convention aus Base.metadata (siehe
        # alembic/env.py target_metadata) und interpoliert sie zu ck_smtp_settings_<suffix>.
        # Siehe Migration 0014 für die ausführliche Erklärung/Verifikation dieses Verhaltens.
        sa.CheckConstraint("id = 1", name="singleton"),
        sa.CheckConstraint("encryption IN ('starttls', 'ssl')", name="encryption"),
    )


def downgrade() -> None:
    op.drop_table("smtp_settings")
