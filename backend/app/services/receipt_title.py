"""
Regelbasiertes Fallback-Template für den Beleg-Titel (siehe concepts/beleg-titel.md),
greift wenn die KI keinen `suggested_title` liefert (null, kein Anbieter konfiguriert,
needs_review) oder für den einmaligen Backfill (app/scripts/backfill_receipt_titles.py).
Bewusst kein KI-Aufruf hier — nur das deterministische Format `{Kategorie-Label} vom
DD.MM.YYYY`. Die KW-Nuance aus dem Konzept ist bewusst nur eine KI-Stilentscheidung, kein
Teil dieses Regelwerks (siehe Konzept Abschnitt 6).

Eigene, minimale deutsche Kategorie-Label-Zuordnung statt Duplizierung der vollen
frontend/src/lib/categories.ts-Struktur (Farben/Zusatzfelder sind hier irrelevant). Die
Kategorie-Werteliste selbst bleibt Single Point of Truth in
app/schemas/receipt.py::ReceiptCategory — dieses Dict deckt nur deren Anzeigenamen ab und
fällt bei unbekannten/neuen Werten auf den generischen Label zurück statt zu crashen.
"""

from datetime import date

CATEGORY_LABELS_DE: dict[str, str] = {
    "electronics": "Elektronik",
    "groceries": "Lebensmittel",
    "travel": "Reisen",
    "furniture": "Möbel",
    "fashion": "Mode",
    "dining": "Restaurant",
    "fuel": "Tanken",
    "health": "Gesundheit",
    "drugstore": "Drogerie",
    "leisure": "Freizeit",
    "household": "Haushalt",
    "kids": "Kinder & Baby",
    "pets": "Tierbedarf",
    "other": "Sonstiges",
}

_FALLBACK_LABEL = "Beleg"


def build_fallback_title(category: str | None, receipt_date: date | None) -> str | None:
    """
    `{Kategorie-Label} vom DD.MM.YYYY`, z.B. "Drogerie vom 05.08.2026". Ohne bekanntes
    Belegdatum lässt sich kein sinnvoller Titel bilden — dann None; die bestehende
    Frontend-Fallback-Kette (title ?? ai_suggested_title ?? merchant_name ?? "Beleg vom
    {receipt_date}") übernimmt die Anzeige in dem Fall ohnehin.
    """
    if receipt_date is None:
        return None
    label = CATEGORY_LABELS_DE.get(category, _FALLBACK_LABEL) if category else _FALLBACK_LABEL
    return f"{label} vom {receipt_date.strftime('%d.%m.%Y')}"
