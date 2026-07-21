"""totp: users.totp_secret verbreitern, totp_recovery_codes anlegen

Revision ID: 0013
Revises: 0012
Create Date: 2026-07-21

Teil von Phase 2 des Security-Hardening-Plans (TOTP/2FA). `users.totp_secret` war bisher
auf String(64) ausgelegt (Klartext-Base32-Secret, wie `pyotp` es erzeugt) — das Backend
verschlüsselt das Secret jedoch über Fernet (analoges Muster zu
`ai_settings.encrypted_api_key`), dessen Ciphertext länger als der Klartext ist. Reine
Verbreiterung ohne Datenmigration: die Spalte ist seit ihrer Anlage (v0.3.0) bei jedem
bestehenden User NULL, bislang ungenutzt.

`totp_recovery_codes` als eigene Tabelle statt JSONB-Array auf `users`, damit das
"verbraucht"-Markieren eines einzelnen Codes atomar ist (`UPDATE ... WHERE used_at IS
NULL RETURNING ...`) statt eines Read-Modify-Write-Zyklus auf einem JSONB-Blob, der bei
parallelem Verbrauchsversuch (z.B. zwei Tabs/Geräten) eine Race-Bedingung wäre. "Recovery-
Codes neu generieren" läuft entsprechend über Delete-all+Insert-all statt In-Place-Edit.

Downgrade-Hinweis: das Zurückschmälern von totp_secret auf String(64) schlägt fehl, falls
zu diesem Zeitpunkt bereits ein längerer Fernet-Ciphertext gespeichert wurde (Postgres
prüft die Längen-Constraint beim ALTER COLUMN TYPE) — das ist beabsichtigt (kein stiller
Datenverlust durch Trunkierung), nicht ein Bug dieser Migration.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0013"
down_revision: Union[str, None] = "0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "users",
        "totp_secret",
        existing_type=sa.String(64),
        type_=sa.String(255),
        existing_nullable=True,
    )

    op.create_table(
        "totp_recovery_codes",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code_hash", sa.String(255), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_totp_recovery_codes"),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_totp_recovery_codes_user_id",
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_totp_recovery_codes_user_id",
        "totp_recovery_codes",
        ["user_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_totp_recovery_codes_user_id", table_name="totp_recovery_codes")
    op.drop_table("totp_recovery_codes")

    op.alter_column(
        "users",
        "totp_secret",
        existing_type=sa.String(255),
        type_=sa.String(64),
        existing_nullable=True,
    )
