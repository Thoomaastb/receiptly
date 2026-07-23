"""receipt_shares: öffentliche Freigabe-Links für einzelne Belege

Revision ID: 0020
Revises: 0019
Create Date: 2026-07-23

Teil des Beleg-Teilen-Plans (Roadmap-Priorität 3, siehe
concepts/beleg-teilen.md). Ein Haushaltsmitglied kann für einen einzelnen Beleg einen
anonymen Freigabe-Link erzeugen (z.B. für Versicherung/Handel bei Reklamation), ohne dem
Empfänger einen Account einzuräumen.

`token_hash` ist SHA-256 (hex, immer genau 64 Zeichen), NICHT Argon2id wie bei
Recovery-Codes/Passwörtern (`app/auth/security.py`). Das ist bewusst und keine
Inkonsistenz: Argon2id salzt pro Aufruf, ein Lookup "gegeben nur der Token, finde die
Zeile" (der einzige Zugriffspfad hier — anders als Login/Recovery-Code, wo gegen eine
bereits bekannte Zeile verglichen wird) wäre damit strukturell unmöglich, ohne über die
gesamte Tabelle zu scannen. SHA-256 ist deterministisch und damit per Unique-Index in
O(log n) lookupbar. Der Token selbst hat 256 Bit Entropie (`secrets.token_urlsafe(32)`),
Argon2s Langsamkeit brächte hier keinen Sicherheitsgewinn, nur unnötige CPU-Last auf
einem öffentlichen, unauthentifizierten Endpoint. Ein künftiger Maintainer, der das aus
Konsistenzgründen zu Argon2 "korrigieren" möchte: bitte nicht — das würde den
Hot-Path-Lookup brechen.

`household_id` wird bei Erstellung denormalisiert aus dem Beleg/Bucket übernommen statt
über `receipt_id` nachgeschlagen zu werden — spart einen Join beim Schreiben des
anonymen `share_link_accessed`-Audit-Events, das (da es keinen eingeloggten Nutzer gibt)
sonst keinen anderen Weg zur `household_id` hätte.

`created_by ON DELETE CASCADE` analog zum Präzedenzfall `Notification.user_id`
(`0018_notifications.py`) — ein gelöschter User nimmt seine erstellten Freigabe-Links
mit, statt sie verwaist zurückzulassen.

Anders als `audit_log` gibt es hier KEINEN Immutability-Trigger — `revoked_at`,
`accessed_at` und `access_count` sind gezielt von der Anwendungslogik mutierte Felder
(Widerruf, Verbrauchs-Tracking), kein Beweismittel-Log. Das ist eine ganz normale
veränderliche Tabelle, wie die meisten anderen im Projekt. Nur `created_at` existiert
als Zeitstempel (kein `updated_at`) — `revoked_at`/`accessed_at` sind eigene, gezielt
gesetzte Zeitpunkte, kein generisches "zuletzt geändert".

Indizes: Unique auf `token_hash` (Hot-Path-Lookup für `GET /share/{token}` und
`.../file`, beide unauthentifiziert und damit besonders latenzsensitiv), Index auf
`receipt_id` (bedient die "aktive Links für diesen Beleg"-Liste, die 10-Links-Cap-
Zählung pro Beleg und ein effizientes `ON DELETE CASCADE` von `receipts`).
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
