import re
from dataclasses import dataclass
from datetime import UTC, date, datetime

# Deckt die gängigen Trenner (Punkt/Bindestrich/Slash) und beide Jahresformate ab. Bewusst
# NICHT auf ein bestimmtes Trennzeichen oder 4-stellige Jahre eingeschränkt, damit sowohl
# "25.12.2025" als auch "25-12-25" oder "25/12/25" erkannt werden — der Plausibilitäts-Check
# unten (Tag/Monat-Grenzen, keine Zukunft) filtert danach falsche Treffer wie Uhrzeiten oder
# Bonnummern aus, die zufällig ins Muster passen.
_DATE_PATTERN = re.compile(r"\b(\d{1,2})[.\-/](\d{1,2})[.\-/](\d{2,4})\b")

# Nur Zeilen mit einem dieser Keywords kommen als Quelle für den Gesamtbetrag infrage —
# bewusst KEIN "größte Zahl im Text"-Fallback (zu hohe False-Positive-Gefahr durch
# Einzelpositionen, Rabatte, Pfand etc.), lieber None als raten.
_AMOUNT_LINE_KEYWORDS = re.compile(r"SUMME|TOTAL|GESAMT(BETRAG)?|ZU ZAHLEN|BETRAG", re.IGNORECASE)

# Deutsches Zahlenformat: Tausenderpunkte optional, Komma als Dezimaltrennzeichen Pflicht —
# verhindert, dass z.B. eine Steuernummer oder ein Datum fälschlich als Betrag gelesen wird.
_AMOUNT_PATTERN = re.compile(r"\d{1,3}(?:\.\d{3})*,\d{2}")

_EUR_SYMBOL_PATTERN = re.compile(r"€")
_EUR_CODE_PATTERN = re.compile(r"\bEUR\b", re.IGNORECASE)


@dataclass
class HeuristicResult:
    receipt_date: date | None
    total_amount: float | None
    currency: str | None


def _extract_date(raw_text: str) -> date | None:
    today = datetime.now(UTC).date()
    for day_str, month_str, year_str in _DATE_PATTERN.findall(raw_text):
        day, month = int(day_str), int(month_str)
        if day < 1 or day > 31 or month < 1 or month > 12:
            continue
        year = int(year_str)
        if len(year_str) == 2:
            year += 2000
        try:
            candidate = date(year, month, day)
        except ValueError:
            continue
        if candidate > today:
            continue
        return candidate
    return None


def _extract_amount(raw_text: str) -> float | None:
    for line in raw_text.splitlines():
        if not _AMOUNT_LINE_KEYWORDS.search(line):
            continue
        match = _AMOUNT_PATTERN.search(line)
        if match is None:
            continue
        normalized = match.group(0).replace(".", "").replace(",", ".")
        try:
            return float(normalized)
        except ValueError:
            continue
    return None


def _extract_currency(raw_text: str) -> str | None:
    if _EUR_SYMBOL_PATTERN.search(raw_text):
        return "EUR"
    if _EUR_CODE_PATTERN.search(raw_text):
        return "EUR"
    return None


def extract_receipt_heuristics(raw_text: str | None) -> HeuristicResult:
    """
    Regex-basierte Fallback-Vorbefüllung für Datum/Betrag/Währung, wenn keine KI-Extraktion
    verfügbar ist oder diese fehlschlägt. Python-Pendant zur clientseitigen TS-Heuristik
    (frontend/src/lib/ocr/heuristics.ts, separater Frontend-Schritt) für Fälle, in denen der
    Client kein OCR ausführt (PDF-Uploads). Reine Funktion ohne DB-/Async-Abhängigkeit.
    """
    if not raw_text or not raw_text.strip():
        return HeuristicResult(receipt_date=None, total_amount=None, currency=None)

    return HeuristicResult(
        receipt_date=_extract_date(raw_text),
        total_amount=_extract_amount(raw_text),
        currency=_extract_currency(raw_text),
    )
