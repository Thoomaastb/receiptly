"""ai_usage_events: globaler KI-Token-/Kosten-Log für den Admin-Zähler

Revision ID: 0009
Revises: 0008
Create Date: 2026-07-17

Ein Log-Eintrag pro KI-Extraktions-Call, systemweit (bewusst KEIN household_id — der
geplante Admin-Zähler summiert Token-Verbrauch/Kosten über die gesamte Instanz, nicht
pro Haushalt). Zeilen sind unveränderlich (nur created_at), daher kein updated_at.

provider ist ein freier String statt eines Enum-Typs — Log-Zeilen sollen unabhängig von
künftigen Änderungen an den unterstützten Provider-Werten lesbar bleiben (siehe die
Enum-Migrationsprobleme in 0008). estimated_cost_usd ist nullable, weil bei einem nicht
erkannten Modellnamen kein Preis-Mapping existiert und NULL dem "unbekannt" ehrlicher
entspricht als ein geschätzter Platzhalterwert.

Index nur auf created_at (für künftige Zeitraum-Filter) — Lesezugriffe sind aktuell ein
einfaches SUM(...) über die gesamte Tabelle, keine Einzelzeilen-Lookups, daher keine
weiteren Indizes.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ai_usage_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("model", sa.String(255), nullable=False),
        sa.Column("prompt_tokens", sa.Integer(), nullable=False),
        sa.Column("completion_tokens", sa.Integer(), nullable=False),
        sa.Column("total_tokens", sa.Integer(), nullable=False),
        sa.Column("estimated_cost_usd", sa.Numeric(10, 6), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_ai_usage_events"),
    )
    op.create_index("ix_ai_usage_events_created_at", "ai_usage_events", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_ai_usage_events_created_at", table_name="ai_usage_events")
    op.drop_table("ai_usage_events")
