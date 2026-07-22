"""notifications: In-App-Benachrichtigungen (Garantie-Ablauf, Sicherheitshinweise)

Revision ID: 0018
Revises: 0017
Create Date: 2026-07-22

Teil des Benachrichtigungssystem-Plans (Roadmap-Priorität 2, siehe
concepts/benachrichtigungssystem.md). Speichert pro Empfänger eine eigene Zeile — auch
bei haushaltsweiten Ereignissen (z.B. Passkey-Exklusiv-Login-Toggle) wird für jedes
Haushaltsmitglied ein eigener Datensatz erzeugt, keine gemeinsame Zeile mit Auflösung zur
Laufzeit.

Anders als `audit_log` (siehe `0012_audit_log.py` und `app/models/audit_log.py`) ist
diese Tabelle bewusst NICHT immutable — es gibt hier keinen Immutability-Trigger. Zwei
Gründe, beide strukturell, nicht Nachlässigkeit:
  1. `read_at` wird von der Anwendung mutiert, sobald ein Nutzer eine Benachrichtigung
     liest (`POST /notifications/{id}/read`) — ein UPDATE ist der Kernzweck der Spalte.
  2. Ein Retention-Cleanup-Job (`scripts/cleanup_notifications.py`) muss gelesene,
     abgelaufene Zeilen per DELETE entfernen (90-Tage-Grenze, Q9) — auch das ist
     erwartetes Verhalten, kein Bug, den ein Trigger verhindern müsste.
`audit_log` ist als Beweismittel für "was ist tatsächlich passiert" bewusst
unveränderlich; `notifications` ist reiner Nutzer-UI-Zustand und folgt deshalb dem
Standard-Muster (keine Trigger, wie die meisten anderen Tabellen im Projekt).

`category`/`type` sind bewusst plain `String`, kein Postgres-Enum — dieselbe Begründung
wie bei `audit_log.event_type`: neue Werte sollen ohne `ALTER TYPE ... ADD VALUE` bzw.
Migration möglich sein. Die v1-Werteliste wird nur in Python
(`app/services/notifications.py`) als Konstante geführt.

`uq_notifications_user_id_dedup_key` ist die Idempotenz-Basis für das ganze Feature: ein
scheduled Job (Garantie-Scan) und der Audit-Log-Hook (Sicherheitshinweise) inserten beide
via `ON CONFLICT (user_id, dedup_key) DO NOTHING`. Postgres behandelt NULL in
Unique-Indizes als paarweise verschieden — das betrifft hier keine Zeile, da jeder
v1-Notification-Typ immer einen `dedup_key` setzt.

Die beiden weiteren Indizes bedienen die beiden Haupt-Lesepfade: die paginierte
"Alle"-Liste (`user_id, created_at`) und den Ungelesen-Zähler global wie pro Kategorie
(`user_id, category, read_at`) — Letzterer deckt sowohl `WHERE user_id=? AND read_at IS
NULL` als auch dieselbe Query mit zusätzlichem `category`-Gleichheitsfilter ab.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0018"
down_revision: Union[str, None] = "0017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("household_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("type", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("link", sa.String(length=500), nullable=True),
        sa.Column("dedup_key", sa.String(length=255), nullable=True),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_notifications"),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_notifications_user_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["household_id"],
            ["households.id"],
            name="fk_notifications_household_id",
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "uq_notifications_user_id_dedup_key",
        "notifications",
        ["user_id", "dedup_key"],
        unique=True,
    )
    op.create_index(
        "ix_notifications_user_id_created_at",
        "notifications",
        ["user_id", "created_at"],
    )
    op.create_index(
        "ix_notifications_user_id_category_read_at",
        "notifications",
        ["user_id", "category", "read_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_notifications_user_id_category_read_at", table_name="notifications")
    op.drop_index("ix_notifications_user_id_created_at", table_name="notifications")
    op.drop_index("uq_notifications_user_id_dedup_key", table_name="notifications")
    op.drop_table("notifications")
