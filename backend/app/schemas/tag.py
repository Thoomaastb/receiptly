import uuid
from typing import Literal

from pydantic import BaseModel, Field

# Platzhalter-Slots einer festen Farbpalette (Frontend-Konstante + CSS-Tokens --color-tag-*
# kommen erst in einem späteren Designer-Schritt) — hier nur der Vertrag, welche Slot-Keys
# gültig sind. Spiegelt Tag.color in app/models/tag.py (String-Spalte ohne DB-Constraint,
# die Validierung der erlaubten Werte läuft ausschließlich hier).
TagColor = Literal[
    "tag-01", "tag-02", "tag-03", "tag-04", "tag-05", "tag-06", "tag-07", "tag-08",
    "tag-09", "tag-10", "tag-11", "tag-12", "tag-13", "tag-14", "tag-15", "tag-16",
    "tag-17", "tag-18", "tag-19", "tag-20", "tag-21", "tag-22", "tag-23", "tag-24",
]


class TagResponse(BaseModel):
    id: uuid.UUID
    name: str
    color: str

    model_config = {"from_attributes": True}


class TagCreate(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    color: TagColor


class TagUpdate(BaseModel):
    """Alle Felder optional — nur mitgeschickte Felder werden geändert (siehe update_tag)."""

    name: str | None = Field(default=None, min_length=1, max_length=50)
    color: TagColor | None = None
