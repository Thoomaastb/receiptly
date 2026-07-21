"""audit_log: immutable append-only Sicherheits-Audit-Tabelle

Revision ID: 0012
Revises: 0011
Create Date: 2026-07-20

Teil von Phase 1 des Security-Hardening-Plans (Rate-Limiting + Audit-Log). Protokolliert
sicherheitsrelevante Ereignisse (Login-Erfolg/-Fehlschlag, Passwortänderung, Session-
Beendigung, Rate-Limit-Treffer, ...) pro Haushalt.

Immutability via Trigger mit Session-GUC-Bypass statt hartem Verbot ohne Ausweg: ein
reines "verbiete jedes UPDATE/DELETE" hätte keinen Weg für eine spätere, policy-
gesteuerte Retention-Löschung (kommt in Phase 2, `cleanup_audit_log.py`). Stattdessen
prüft der Trigger die Session-GUC `audit.allow_delete` — nur wenn sie in der aktuellen
Transaktion explizit auf 'true' gesetzt wurde, lässt der Trigger die Operation durch.
Normale API-Request-DB-Sessions setzen diese GUC nie und sind damit strukturell unfähig,
audit_log-Zeilen zu ändern/löschen, selbst bei einem Bug im App-Code.

WICHTIG für künftige Migrationen, die audit_log-Zeilen selbst anfassen müssen (z.B. ein
Rename von event_type-Werten): sie müssen in ihrer eigenen Transaktion selbst
`SET LOCAL audit.allow_delete = 'true'` setzen — dieselbe GUC gilt für UPDATE und DELETE
(siehe Trigger-Funktion unten, `COALESCE(NEW, OLD)`), sonst schlagen sie am eigenen
Trigger fehl. Beispiel:
    op.execute(sa.text("SET LOCAL audit.allow_delete = 'true'"))
    op.execute(sa.text("UPDATE audit_log SET ..."))

id folgt der Projekt-Konvention aus allen anderen Tabellen (siehe z.B. app/models/user.py,
app/models/receipt.py): Python-seitiges `default=uuid.uuid4` statt server_default
gen_random_uuid() — kein Precedent im Projekt für Postgres-seitige UUID-Generierung.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0012"
down_revision: Union[str, None] = "0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "audit_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "household_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("ip", sa.String(64), nullable=True),
        sa.Column("user_agent", sa.String(300), nullable=True),
        sa.Column("attempted_username", sa.String(64), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_audit_log"),
        sa.ForeignKeyConstraint(
            ["household_id"],
            ["households.id"],
            name="fk_audit_log_household_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_audit_log_user_id",
            ondelete="SET NULL",
        ),
    )
    op.create_index(
        "ix_audit_log_household_id_created_at",
        "audit_log",
        ["household_id", sa.text("created_at DESC")],
    )
    op.create_index(
        "ix_audit_log_user_id_created_at",
        "audit_log",
        ["user_id", sa.text("created_at DESC")],
    )

    op.execute(
        sa.text(
            """
            CREATE FUNCTION audit_log_immutable_trigger() RETURNS trigger AS $$
            BEGIN
              IF current_setting('audit.allow_delete', true) = 'true' THEN
                RETURN COALESCE(NEW, OLD);
              END IF;
              RAISE EXCEPTION 'audit_log ist append-only: % nicht erlaubt', TG_OP;
            END;
            $$ LANGUAGE plpgsql;
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE TRIGGER audit_log_prevent_update
            BEFORE UPDATE ON audit_log
            FOR EACH ROW EXECUTE FUNCTION audit_log_immutable_trigger();
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE TRIGGER audit_log_prevent_delete
            BEFORE DELETE ON audit_log
            FOR EACH ROW EXECUTE FUNCTION audit_log_immutable_trigger();
            """
        )
    )


def downgrade() -> None:
    op.execute(sa.text("DROP TRIGGER IF EXISTS audit_log_prevent_delete ON audit_log"))
    op.execute(sa.text("DROP TRIGGER IF EXISTS audit_log_prevent_update ON audit_log"))
    op.execute(sa.text("DROP FUNCTION IF EXISTS audit_log_immutable_trigger()"))

    op.drop_index("ix_audit_log_user_id_created_at", table_name="audit_log")
    op.drop_index("ix_audit_log_household_id_created_at", table_name="audit_log")
    op.drop_table("audit_log")
