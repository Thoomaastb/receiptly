"""ai_settings: Provider-Enum-Rework (custom raus, google rein), provider nullable,
custom_endpoint -> endpoint_url

Revision ID: 0008
Revises: 0007
Create Date: 2026-07-15

custom_endpoint deckte bisher zwei verschiedene Bedürfnisse ab (haushaltseigene
Ollama-Instanz vs. beliebiger OpenAI-kompatibler Drittanbieter). Der generische
Custom-Provider entfällt ersatzlos, die Spalte wird zu endpoint_url (nur noch für die
Ollama/Lokal-Auswahl relevant). provider verliert NOT NULL + Default "ollama": NULL
bedeutet ab jetzt explizit "kein Haushalts-Provider konfiguriert" (Prioritätskette mit
server-weiter .env-Konfiguration, siehe app/services/ai_provider_resolution.py).

Postgres kann Enum-Werte nicht direkt entfernen (nur ADD VALUE ist nativ unterstützt,
nicht DROP VALUE) — daher Typ-Neuanlage: neuen Typ mit der Ziel-Wertemenge anlegen, Spalte
per USING-Cast umhängen, alten Typ droppen, neuen umbenennen. Der DEFAULT-Ausdruck der
Spalte (server_default='ollama' auf dem alten Typ) muss VOR dem TYPE-Wechsel entfernt
werden — Postgres versucht sonst, den bestehenden Default-Ausdruck auf den neuen Typ zu
casten, was zwischen zwei eigenständigen Enum-Typen ohne expliziten Cast fehlschlägt
("default for column ... cannot be cast automatically to type ...").

Downgrade-Hinweis: Zeilen mit provider='google' können beim Downgrade nicht auf den alten
Enum-Typ (ohne 'google') zurückgecastet werden und lassen die Migration mit einem
Postgres-Fehler scheitern ("invalid input value for enum ai_provider_type: google"). In
der Praxis unkritisch, da ein Downgrade dieses Pakets nur unmittelbar nach einem
fehlgeschlagenen Deploy gefahren würde, bevor irgendwelche Google-Konfigurationen
existieren — trotzdem hier vermerkt, falls doch mal danach downgegradet wird.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

OLD_ENUM_VALUES = ("ollama", "openai", "anthropic", "custom")
NEW_ENUM_VALUES = ("ollama", "openai", "anthropic", "google")


def upgrade() -> None:
    # NOT NULL zuerst lösen — die anschließende UPDATE-Neutralisierung von custom-Zeilen
    # setzt provider auf NULL und würde sonst (noch auf dem alten NOT-NULL-Constraint)
    # fehlschlagen. Default ebenfalls hier schon entfernen (siehe Docstring), beides ist
    # vom Enum-Typ unabhängig und muss nicht auf den Typ-Umbau warten.
    op.alter_column(
        "ai_settings",
        "provider",
        existing_type=sa.Enum(*OLD_ENUM_VALUES, name="ai_provider_type"),
        server_default=None,
        nullable=True,
    )

    # Bestehende custom-Zeilen neutralisieren, bevor der Enum-Typ verengt wird (in der
    # Praxis vermutlich 0 Zeilen betroffen — die Inference-Pipeline existierte bisher
    # nicht, decrypt_secret() wurde nie aufgerufen).
    op.execute(
        "UPDATE ai_settings SET provider = NULL, custom_endpoint = NULL "
        "WHERE provider = 'custom'"
    )

    new_enum = sa.Enum(*NEW_ENUM_VALUES, name="ai_provider_type_v2")
    new_enum.create(op.get_bind())
    op.execute(
        "ALTER TABLE ai_settings ALTER COLUMN provider TYPE ai_provider_type_v2 "
        "USING provider::text::ai_provider_type_v2"
    )
    op.execute("DROP TYPE ai_provider_type")
    op.execute("ALTER TYPE ai_provider_type_v2 RENAME TO ai_provider_type")

    op.alter_column("ai_settings", "custom_endpoint", new_column_name="endpoint_url")


def downgrade() -> None:
    op.alter_column("ai_settings", "endpoint_url", new_column_name="custom_endpoint")

    old_enum = sa.Enum(*OLD_ENUM_VALUES, name="ai_provider_type_v1")
    old_enum.create(op.get_bind())
    op.execute(
        "ALTER TABLE ai_settings ALTER COLUMN provider TYPE ai_provider_type_v1 "
        "USING provider::text::ai_provider_type_v1"
    )
    op.execute("DROP TYPE ai_provider_type")
    op.execute("ALTER TYPE ai_provider_type_v1 RENAME TO ai_provider_type")

    # NOT NULL braucht einen Wert für bereits vorhandene NULL-Zeilen (z.B. Haushalte, die
    # unter 0008 bewusst "kein Provider" gewählt hatten) — sonst schlägt SET NOT NULL fehl.
    op.execute("UPDATE ai_settings SET provider = 'ollama' WHERE provider IS NULL")
    op.alter_column(
        "ai_settings",
        "provider",
        existing_type=sa.Enum(*OLD_ENUM_VALUES, name="ai_provider_type"),
        server_default="ollama",
        nullable=False,
    )
