"""Tags: haushaltseigene Labels + Many-to-Many-Verknüpfung mit Belegen

Revision ID: 0024
Revises: 0023
Create Date: 2026-07-25

Erste DB-Infrastruktur für das Feature "Tags" (siehe concepts/tags.md, Plan-Schritt B1).
Tags sind frei vergebene, haushaltseigene Labels — eine Ergänzung zur strukturierten
Kategorie (`receipts.category`, siehe Migration 0023), kein globaler Katalog wie bei
`merchants`. `tags` gehört pro Zeile genau einem Haushalt (`household_id`, ON DELETE
CASCADE), die Zuordnung zu Belegen läuft über die reine Join-Tabelle `receipt_tags`
(Composite-PK aus beiden FKs, beide ON DELETE CASCADE) ohne eigenes ORM-Assoziationsobjekt
— es gibt kein Attribut auf der Verknüpfung selbst, das die App lesen/schreiben muss.

`uq_tags_household_normalized_name` verhindert doppelte Tags (case-/whitespace-
normalisiert, Normalisierung erfolgt in der Service-Schicht) innerhalb eines Haushalts,
erlaubt aber denselben Tag-Namen in verschiedenen Haushalten. Bewusst kein DB-Enum/CHECK-
Constraint auf `color`: die Farbpalette ist eine Frontend-Konstante, die wachsen kann,
ohne dass das an eine Migration gekoppelt sein soll (gleiches Muster wie die Kategorie-
Whitelist in 0023).

Beide Tabellen sind komplett neu (kein Backfill nötig) — additiv, kein Table-Rewrite.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0024"
down_revision: Union[str, None] = "0023"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tags",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("household_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column("normalized_name", sa.String(length=50), nullable=False),
        sa.Column("color", sa.String(length=20), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_tags"),
        sa.ForeignKeyConstraint(
            ["household_id"],
            ["households.id"],
            name="fk_tags_household_id",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "household_id",
            "normalized_name",
            name="uq_tags_household_normalized_name",
        ),
    )
    op.create_index("ix_tags_household_id", "tags", ["household_id"])

    op.create_table(
        "receipt_tags",
        sa.Column("receipt_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tag_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("receipt_id", "tag_id", name="pk_receipt_tags"),
        sa.ForeignKeyConstraint(
            ["receipt_id"],
            ["receipts.id"],
            name="fk_receipt_tags_receipt_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tag_id"],
            ["tags.id"],
            name="fk_receipt_tags_tag_id",
            ondelete="CASCADE",
        ),
    )


def downgrade() -> None:
    op.drop_table("receipt_tags")
    op.drop_index("ix_tags_household_id", table_name="tags")
    op.drop_table("tags")
