import uuid

from sqlalchemy import Column, DateTime, ForeignKey, String, Table, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.mixins import TimestampMixin

# Plain Core-Table statt eigener ORM-Klasse für die Join-Tabelle — bewusst ANDERS als
# BucketAccess (dort begründet der queryable/updatable access_level eine echte Mapped-
# Klasse mit Composite-PK). receipt_tags hat kein solches Attribut, das die App lesen/
# schreiben muss — eine Mischung aus Assoziations-Objekt-Klasse UND secondary=-
# Relationship auf derselben Tabelle kann bei Flushes zu doppelten Inserts führen, daher
# hier von vornherein ein reiner secondary=-Table.
receipt_tags = Table(
    "receipt_tags",
    Base.metadata,
    Column("receipt_id", UUID(as_uuid=True), ForeignKey("receipts.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", UUID(as_uuid=True), ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
    Column("created_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
)


class Tag(Base, TimestampMixin):
    """
    Frei vergebene, haushaltseigene Labels — Ergänzung zur strukturierten Kategorie
    (Receipt.category), kein globaler Katalog wie bei Merchant (siehe Konzept
    concepts/tags.md).
    """

    __tablename__ = "tags"
    __table_args__ = (UniqueConstraint("household_id", "normalized_name", name="uq_tags_household_normalized_name"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    household_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("households.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(50), nullable=False)
    # Referenziert einen Slot einer festen Farbpalette (Frontend-Konstante + CSS-Tokens
    # --color-tag-*, kommt in einem späteren Schritt), kein Hex-Wert. Pflichtfeld ohne
    # DB-Default: Farbwahl ist beim Anlegen ein Ein-Klick-Vorgang (Swatch-Picker), ein
    # impliziter Default würde nur bedeuten, dass viele Tags versehentlich dieselbe
    # Farbe bekommen.
    color: Mapped[str] = mapped_column(String(20), nullable=False)

    receipts: Mapped[list["Receipt"]] = relationship(secondary=receipt_tags, back_populates="tags")  # noqa: F821
