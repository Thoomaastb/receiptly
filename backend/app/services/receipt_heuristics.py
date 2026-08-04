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

# Deutsche Kassenbons weisen praktisch immer eine MwSt-/USt-Aufschlüsselungstabelle aus
# (Steuersatz % + Netto + Brutto je Steuerklasse, endend in einer Summe-/Gesamt-Zeile) —
# diese Steuer ist bereits im Gesamtbetrag enthalten, nie zusätzlich. Die KI hält sich
# trotz expliziter Prompt-Anweisung (siehe ai_extraction.py::_SYSTEM_PROMPT) live nicht
# zuverlässig daran und setzt tax_amount fälschlich auf die Brutto-Summe dieser Tabelle
# (live an einem echten LIDL-Bon verifiziert) — dieser deterministische Fallback erkennt
# das Muster, damit ai_extraction.py das fälschliche tax_amount überschreiben kann.
_VAT_KEYWORD_PATTERN = re.compile(r"MWST|USt\b", re.IGNORECASE)

# "Summe"/"Gesamt" als Abschlusszeile der Tabelle — bewusst nicht an Zeilenanfang
# verankert, da OCR führende Leerzeichen/Tabs uneinheitlich erkennt.
_VAT_SUMMARY_LINE_PATTERN = re.compile(r"SUMME|GESAMT", re.IGNORECASE)

# Wie viele Zeilen vor der Summe-Zeile nach dem MWST-Signalwort gesucht wird — deckt die
# übliche Kopfzeile ("MWST% MWST + Netto = Brutto") und die Steuersatz-Zeilen davor ab,
# ohne beliebig weit hochzulaufen und dadurch eine unabhängige Zeile (z.B. eine
# Artikel-Summenzeile weiter oben auf dem Bon) fälschlich als Teil der Tabelle zu werten.
_VAT_KEYWORD_LOOKBACK_LINES = 6


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


def vat_table_gross_matches_total(raw_text: str | None, total_amount: float | None) -> bool:
    """
    Erkennt die deutsche MwSt-/USt-Aufschlüsselungstabelle im OCR-Rohtext und prüft, ob
    ihre Brutto-Summe (dritte Dezimalzahl der Summe-/Gesamt-Zeile: MwSt, Netto, Brutto)
    zum bereits bekannten total_amount passt (Toleranz 0.01 EUR wegen Rundung). Ein
    Treffer belegt, dass die dort ausgewiesene Steuer bereits im Gesamtbetrag enthalten
    ist — genutzt in ai_extraction.py::_apply_extraction_result(), um ein von der KI
    trotz Prompt-Verbot fälschlich gesetztes tax_amount zu überschreiben.
    """
    if not raw_text or total_amount is None:
        return False

    lines = raw_text.splitlines()
    for index, line in enumerate(lines):
        if not _VAT_SUMMARY_LINE_PATTERN.search(line):
            continue
        amounts = _AMOUNT_PATTERN.findall(line)
        if len(amounts) < 3:
            continue

        lookback_start = max(0, index - _VAT_KEYWORD_LOOKBACK_LINES)
        context = "\n".join(lines[lookback_start:index])
        if not _VAT_KEYWORD_PATTERN.search(context):
            continue

        gross_normalized = amounts[2].replace(".", "").replace(",", ".")
        try:
            gross_value = float(gross_normalized)
        except ValueError:
            continue

        if abs(gross_value - total_amount) <= 0.01:
            return True

    return False


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
