"""webauthn_credentials: Passkey/FIDO2-Credentials pro User

Revision ID: 0016
Revises: 0015
Create Date: 2026-07-22

Teil von Phase 3 des Security-Hardening-Plans (Passkeys/WebAuthn, siehe
concepts/security-hardening.md Abschnitt 4.3). 1:n zu `users` — ein User kann mehrere
Passkeys registrieren (Konzept fordert das ausdrücklich als Backup-Redundanz, z.B.
Zweitgerät/Security-Key, besonders relevant sobald der spätere Passkey-Exklusiv-Login
aktiv ist).

`public_key` ist die erste BYTEA-Spalte im Projekt (roher COSE-Public-Key, wie ihn
py_webauthn bei der Registrierung liefert — keine Textkodierung). `credential_id`
dagegen ist Text (Base64url-kodiert vom Authenticator) und trägt die Unique-Constraint,
über die beim Login der passende Credential-Datensatz nachgeschlagen wird.

`sign_count` startet bei 0 und wird beim späteren Login-Verify für die Clone-Detection
fortgeschrieben (Anwendungslogik, nicht Teil dieser Migration).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0016"
down_revision: Union[str, None] = "0015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "webauthn_credentials",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("credential_id", sa.String(length=1024), nullable=False),
        sa.Column("public_key", sa.LargeBinary(), nullable=False),
        sa.Column("sign_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("transports", sa.String(length=255), nullable=True),
        sa.Column("device_label", sa.String(length=100), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_webauthn_credentials"),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_webauthn_credentials_user_id",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("credential_id", name="uq_webauthn_credentials_credential_id"),
    )
    op.create_index(
        "ix_webauthn_credentials_user_id",
        "webauthn_credentials",
        ["user_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_webauthn_credentials_user_id", table_name="webauthn_credentials")
    op.drop_table("webauthn_credentials")
