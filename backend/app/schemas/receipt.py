import uuid
from datetime import date, datetime
from typing import Any, Literal, get_args

from pydantic import BaseModel, Field

from app.schemas.tag import TagResponse

# Single Point of Truth für gültige Kategorie-Werte (siehe concepts/kategorie-neuordnung.md).
# 7 bestehende Werte zuerst unverändert, dann 6 neue, "other" als Catch-all ans Ende.
ReceiptCategory = Literal[
    "electronics",
    "groceries",
    "travel",
    "furniture",
    "fashion",
    "dining",
    "fuel",
    "health",
    "drugstore",
    "leisure",
    "household",
    "kids",
    "pets",
    "other",
]
ALLOWED_CATEGORY_VALUES: frozenset[str] = frozenset(get_args(ReceiptCategory))


class ReceiptUploadResponse(BaseModel):
    id: uuid.UUID
    bucket_id: uuid.UUID
    status: str
    file_path: str
    content_hash: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ItemResponse(BaseModel):
    id: uuid.UUID
    raw_name: str
    quantity: float
    unit: str | None
    unit_price: float | None
    total_price: float
    discount_amount: float | None = Field(default=None, ge=0)
    pack_amount: float | None
    pack_unit: str | None

    model_config = {"from_attributes": True}


class ItemCreate(BaseModel):
    raw_name: str = Field(min_length=1, max_length=255)
    quantity: float = Field(default=1, gt=0)
    unit: str | None = Field(default=None, max_length=20)
    unit_price: float | None = Field(default=None, ge=0)
    total_price: float = Field(ge=0)
    discount_amount: float | None = Field(default=None, ge=0)
    pack_amount: float | None = Field(default=None, gt=0)
    pack_unit: str | None = Field(default=None, max_length=20)


class ItemUpdate(BaseModel):
    raw_name: str | None = Field(default=None, min_length=1, max_length=255)
    quantity: float | None = Field(default=None, gt=0)
    unit: str | None = Field(default=None, max_length=20)
    unit_price: float | None = Field(default=None, ge=0)
    total_price: float | None = Field(default=None, ge=0)
    discount_amount: float | None = Field(default=None, ge=0)
    pack_amount: float | None = Field(default=None, gt=0)
    pack_unit: str | None = Field(default=None, max_length=20)


class ReceiptListItem(BaseModel):
    id: uuid.UUID
    bucket_id: uuid.UUID
    status: str
    receipt_date: date | None
    total_amount: float | None
    currency: str
    thumb_path: str | None
    merchant_name: str | None
    category: str | None
    item_count: int
    created_at: datetime
    tags: list[TagResponse]

    model_config = {"from_attributes": True}


class ReceiptDetail(ReceiptListItem):
    ocr_raw_text: str | None
    ocr_confidence: float | None
    file_path: str
    is_high_value: bool
    warranty_months: int | None
    warranty_expires_at: date | None
    custom_fields: dict[str, Any] | None
    shipping_cost: float | None
    discount_amount: float | None
    tax_amount: float | None
    items: list[ItemResponse]
    # KI-Struktur-Extraktions-Vorschläge (siehe app/services/ai_extraction.py) — Vorschlag,
    # bis der Nutzer ihn per PATCH übernimmt oder verwirft (dismiss_ai_suggestion).
    ai_suggested_merchant_name: str | None
    ai_suggested_category: str | None
    ai_suggested_receipt_date: date | None
    ai_suggested_total_amount: float | None
    ai_suggested_currency: str | None
    ai_extraction_note: str | None
    ai_extracted_at: datetime | None
    # Tag-Vorschläge aus Händler-Historie (siehe app/services/tag_suggestions.py) — reines
    # Lese-Vorschlagsfeld, kein Persistenz-Feld auf Receipt.
    suggested_tags: list[TagResponse]


class ReceiptUpdate(BaseModel):
    """Alle Felder optional — nur mitgeschickte Felder werden geändert (siehe update_receipt)."""

    receipt_date: date | None = None
    total_amount: float | None = Field(default=None, ge=0)
    shipping_cost: float | None = Field(default=None, ge=0)
    discount_amount: float | None = Field(default=None, ge=0)
    tax_amount: float | None = Field(default=None, ge=0)
    # ISO-4217-Code, z.B. "EUR" — None heißt "nicht mitschicken" (unverändert lassen),
    # konsistent mit den übrigen optionalen Feldern hier (siehe update_receipt).
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    merchant_name: str | None = Field(default=None, min_length=1, max_length=255)
    is_high_value: bool | None = None
    warranty_months: int | None = Field(default=None, ge=0, le=600)
    # Kategorie hängt am Merchant, nicht am Receipt (siehe Merchant-Modell) — betrifft also
    # automatisch alle Belege desselben Händlers. Wie merchant_name/warranty_months: None
    # heißt "nicht mitschicken" (unverändert lassen), kein explizites Zurücksetzen über
    # dieses Feld — konsistent mit den übrigen optionalen Feldern hier.
    category: ReceiptCategory | None = None
    # Kategorie-spezifische Zusatzfelder (siehe Receipt.custom_fields) — wie die übrigen
    # Felder hier: komplettes Objekt ersetzt den bisherigen Wert, kein Merge auf Server-Seite.
    custom_fields: dict[str, Any] | None = None
    # Wie custom_fields: None=unverändert, []=alle Tags entfernen, [...]=Komplett-Ersetzen
    # (kein Merge mit bestehenden Tags) — siehe update_receipt.
    tag_ids: list[uuid.UUID] | None = None
    # True verwirft beide ai_suggested_*-Felder (unabhängig davon, ob merchant_name/category
    # in derselben Anfrage übernommen werden) — siehe update_receipt.
    dismiss_ai_suggestion: bool = False

