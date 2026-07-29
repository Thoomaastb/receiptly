"""receipt_shares: öffentliche Freigabe-Links für einzelne Belege

Revision ID: 0020
Revises: 0019
Create Date: 2026-07-23

Ein Haushaltsmitglied kann für einen einzelnen Beleg einen anonymen Freigabe-Link erzeugen
(z.B. für Versicherung/Handel bei Reklamation), ohne dem Empfänger einen Account einzuräumen.

`token_hash` ist SHA-256, NICHT Argon2id wie bei Passwörtern/Recovery-Codes: der einzige
Zugriffspfad hier ist "gegeben nur der Token, finde die Zeile" — mit Argon2ids Salt wäre
das ohne Volltabellen-Scan unmöglich. SHA-256 ist deterministisch und per Unique-Index in
O(log n) lookupbar; der Token selbst hat 256 Bit Entropie (`secrets.token_urlsafe(32)`),
Argon2s Langsamkeit brächte auf diesem öffentlichen Endpoint nur unnötige CPU-Last.

`household_id` wird bei Erstellung denormalisiert aus dem Beleg übernommen — spart einen
Join beim Schreiben des anonymen `share_link_accessed`-Audit-Events (kein eingeloggter
Nutzer, sonst kein anderer Weg zur household_id).

`created_by ON DELETE CASCADE`: ein gelöschter User nimmt seine Freigabe-Links mit, statt
sie verwaist zurückzulassen.

Kein Immutability-Trigger wie bei `audit_log` — `revoked_at`/`accessed_at`/`access_count`
sind gezielt von der Anwendungslogik mutierte Felder, kein Beweismittel-Log.

Indizes: Unique auf `token_hash` (Hot-Path-Lookup für `GET /share/{token}` und `.../file`,
beide unauthentifiziert und latenzsensitiv), Index auf `receipt_id` (aktive-Links-Liste,
10-Links-Cap-Zählung, effizientes ON DELETE CASCADE).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0020"
down_revision: Union[str, None] = "0019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "receipt_shares",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("receipt_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("household_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "single_use", sa.Boolean(), server_default=sa.false(), nullable=False
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("accessed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "access_count", sa.Integer(), server_default="0", nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_receipt_shares"),
        sa.ForeignKeyConstraint(
            ["receipt_id"],
            ["receipts.id"],
            name="fk_receipt_shares_receipt_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["household_id"],
            ["households.id"],
            name="fk_receipt_shares_household_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name="fk_receipt_shares_created_by",
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "uq_receipt_shares_token_hash",
        "receipt_shares",
        ["token_hash"],
        unique=True,
    )
    op.create_index(
        "ix_receipt_shares_receipt_id",
        "receipt_shares",
        ["receipt_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_receipt_shares_receipt_id", table_name="receipt_shares")
    op.drop_index("uq_receipt_shares_token_hash", table_name="receipt_shares")
    op.drop_table("receipt_shares")
