"""update_check_settings: instanzweiter Schalter für automatischen Update-Check

Revision ID: 0026
Revises: 0025
Create Date: 2026-07-27

Analog zu smtp_settings (Migration 0015, siehe dort für die ausführliche Begründung des
Singleton-Musters): kein Haushalts-Konzept, sondern eine instanzweite Einstellung — ob
die Anwendung automatisch auf neue Releases prüft. `id` ist per DEFAULT fix auf 1 gesetzt
und per CHECK-Constraint auf genau diesen Wert beschränkt, was eine zweite Zeile
strukturell verhindert. Im Unterschied zu smtp_settings gibt es hier bewusst kein
.env-Override-Feld/Server-Lock — nur der eine `enabled`-Wert, Default an. Teil von
Plan-Schritt 0a ("Sidebar-Footer: Update-Hinweis") — Router-/Frontend-Anbindung folgt in
separaten Schritten (0b/0c).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0026"
down_revision: Union[str, None] = "0025"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "update_check_settings",
        sa.Column("id", sa.SmallInteger(), server_default="1", nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name="pk_update_check_settings"),
        # Namen bewusst nur der semantische Suffix, nicht der voll qualifizierte Name —
        # op.create_table() übernimmt die naming_convention aus Base.metadata (siehe
        # alembic/env.py target_metadata) und interpoliert sie zu
        # ck_update_check_settings_<suffix>. Siehe Migration 0014/0015 für die
        # ausführliche Erklärung/Verifikation dieses Verhaltens.
        sa.CheckConstraint("id = 1", name="singleton"),
    )


def downgrade() -> None:
    op.drop_table("update_check_settings")
