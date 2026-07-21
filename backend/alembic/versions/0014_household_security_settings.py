"""household_security_settings: haushaltsweite Sicherheitsrichtlinien

Revision ID: 0014
Revises: 0013
Create Date: 2026-07-21

Teil von Phase 2 des Security-Hardening-Plans. Steuert die TOTP-Pflicht auf
Haushaltsebene (`totp_required_for_household`), die Audit-Log-Retention
(`audit_retention_days`) und ob fehlgeschlagene Logins mit unbekanntem Username den
versuchten Usernamen mitloggen (`log_attempted_username`, Datenschutz-Schalter).

Bewusst OHNE `passkey_exclusive_login`-Spalte — kommt erst in einer späteren Phase, wenn
tatsächlich Logik dahintersteht (Lehre aus `users.totp_secret`, das jahrelang ungenutzt
existierte, bevor jetzt in Phase 2 endlich Logik dazukommt — dieses Muster nicht
wiederholen).

id folgt hier keiner eigenen Sequenz: `household_id` ist selbst der Primary Key
(1:1-Beziehung zu `households`, analog zu `ai_settings`), kein separates `id`-Surrogat.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0014"
down_revision: Union[str, None] = "0013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "household_security_settings",
        sa.Column("household_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "totp_required_for_household",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
        sa.Column(
            "audit_retention_days",
            sa.SmallInteger(),
            server_default="90",
            nullable=False,
        ),
        sa.Column(
            "log_attempted_username",
            sa.Boolean(),
            server_default=sa.true(),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("household_id", name="pk_household_security_settings"),
        sa.ForeignKeyConstraint(
            ["household_id"],
            ["households.id"],
            name="fk_household_security_settings_household_id",
            ondelete="CASCADE",
        ),
        # Name bewusst nur der semantische Suffix ("audit_retention_days"), nicht der
        # voll qualifizierte Name: op.create_table() übernimmt die naming_convention aus
        # Base.metadata (siehe alembic/env.py target_metadata), und deren "ck"-Muster
        # ("ck_%(table_name)s_%(constraint_name)s") interpoliert den übergebenen Namen
        # als %(constraint_name)s-Token nach. Ein hier bereits voll qualifizierter Name
        # würde doppelt verschachtelt und bei Überschreitung von 63 Zeichen mit einem
        # Hash-Suffix abgeschnitten (empirisch beim Migrationstest verifiziert).
        sa.CheckConstraint(
            "audit_retention_days IN (30, 90, 180, 365)",
            name="audit_retention_days",
        ),
    )


def downgrade() -> None:
    op.drop_table("household_security_settings")
