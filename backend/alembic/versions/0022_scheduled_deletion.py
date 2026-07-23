"""Konto löschen (DSGVO): scheduled_deletion_at + Platzhalter-User

Revision ID: 0022
Revises: 0021
Create Date: 2026-07-23

Erste Soft-Delete-Infrastruktur im Projekt (siehe concepts/konto-loeschen-datenexport.md).
`scheduled_deletion_at` trägt die gesamte Zustandsmaschine der 14-Tage-Karenzzeit
(NULL = aktiv, gesetzt = Karenzzeit mit Deadline) — bewusst kein eigenes Status-Enum, da ein
reiner nullable Timestamp bereits alles ausdrückt, was gebraucht wird (gleiches Muster wie
`receipt_shares.expires_at`/`totp_recovery_codes.used_at`).

`is_placeholder` markiert einen Tombstone-User pro Haushalt, auf den beim endgültigen
Löschen (Stufe B) die Uploader-Referenz (`receipts.user_id`) verbliebener geteilter Belege
umgeschrieben wird — gewählt statt `receipts.user_id` nullable zu machen, um dessen
bestehende NOT-NULL/CASCADE-Semantik für den Normalfall unangetastet zu lassen (siehe Q12
im Konzept). Partial Unique Index erzwingt höchstens einen Platzhalter pro Haushalt.

Beide Spalten additiv/metadaten-only (`server_default` bei `is_placeholder`, reines NULL bei
`scheduled_deletion_at`) — kein Table-Rewrite, gleiches Muster wie `0017`/`0021`.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0022"
down_revision: Union[str, None] = "0021"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("scheduled_deletion_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column(
            "is_placeholder", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )
    op.create_index(
        "ix_users_scheduled_deletion_at",
        "users",
        ["scheduled_deletion_at"],
        postgresql_where=sa.text("scheduled_deletion_at IS NOT NULL"),
    )
    op.create_index(
        "uq_users_one_placeholder_per_household",
        "users",
        ["household_id"],
        unique=True,
        postgresql_where=sa.text("is_placeholder = true"),
    )


def downgrade() -> None:
    op.drop_index("uq_users_one_placeholder_per_household", table_name="users")
    op.drop_index("ix_users_scheduled_deletion_at", table_name="users")
    op.drop_column("users", "is_placeholder")
    op.drop_column("users", "scheduled_deletion_at")
