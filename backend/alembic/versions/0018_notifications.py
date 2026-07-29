"""notifications: In-App-Benachrichtigungen (Garantie-Ablauf, Sicherheitshinweise)

Revision ID: 0018
Revises: 0017
Create Date: 2026-07-22

Eine Zeile pro Empfänger, auch bei haushaltsweiten Ereignissen — keine gemeinsame Zeile mit
Auflösung zur Laufzeit.

Anders als `audit_log` bewusst NICHT immutable (kein Trigger): `read_at` wird von der App
mutiert (`POST /notifications/{id}/read`), und ein Retention-Cleanup-Job löscht gelesene,
abgelaufene Zeilen (90-Tage-Grenze) — beides normales Verhalten für reinen UI-Zustand,
anders als bei `audit_log` als unveränderliches Beweismittel.

`category`/`type` sind plain `String`, kein Postgres-Enum — neue Werte sollen ohne
Migration möglich sein (Werteliste lebt in `app/services/notifications.py`).

`uq_notifications_user_id_dedup_key` ist die Idempotenz-Basis: sowohl der scheduled
Garantie-Scan als auch der Audit-Log-Hook inserten via `ON CONFLICT ... DO NOTHING`.

Die beiden weiteren Indizes bedienen die paginierte "Alle"-Liste (`user_id, created_at`)
und den Ungelesen-Zähler global/pro Kategorie (`user_id, category, read_at`).
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
