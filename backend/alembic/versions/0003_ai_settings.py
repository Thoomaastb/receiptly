"""ai_settings: household-wide AI provider configuration

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-04

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ai_settings",
        sa.Column("household_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("households.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("provider", sa.Enum("ollama", "openai", "anthropic", "custom", name="ai_provider_type"), nullable=False, server_default="ollama"),
        sa.Column("encrypted_api_key", sa.String(1024), nullable=True),
        sa.Column("custom_endpoint", sa.String(512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("ai_settings")
    sa.Enum(name="ai_provider_type").drop(op.get_bind(), checkfirst=True)
