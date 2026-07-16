import re

# Länder-/Prüfziffern-Prefix + 11-30 weitere alphanumerische Zeichen mit optionalen
# Leerzeichen an beliebiger Stelle — deckt IBAN-Längen 15-34 ab, unabhängig von der
# Gruppierung. WICHTIG: Nicht auf 4er-Blöcke festlegen (`{4}`), sonst rutschen IBANs OHNE
# Leerzeichen durch, deren Restlänge nicht durch 4 teilbar ist (z.B. die deutsche 22-stellige
# IBAN — 18 Zeichen nach dem Prefix, nicht durch 4 teilbar). Trade-off (siehe Plan-Risiken):
# lieber zu aggressiv blanken als ein echtes Muster durchlassen; kann in Einzelfällen auch
# harmlose alphanumerische Codes bzw. angrenzende Tokens mit erfassen.
IBAN_PATTERN = re.compile(r"\b([A-Z]{2}\d{2})(?:[ ]?[A-Z0-9]){11,30}\b")

# Kartennummern-artige Ziffernfolgen (13-19 Stellen, optional durch Leerzeichen/Bindestriche
# getrennt) — deckt gängige Kartenformate ab (Visa/Mastercard 16, Amex 15, ...).
CARD_PATTERN = re.compile(r"\b(?:\d[ -]?){13,19}\b")


def _mask_iban(match: re.Match[str]) -> str:
    prefix = match.group(1)  # Ländercode + Prüfziffern, z.B. "DE44"
    return f"{prefix[:2]}xx " + " ".join(["xxxx"] * 4)


def _mask_card(match: re.Match[str]) -> str:
    digits_only = match.group(0).replace(" ", "").replace("-", "")
    return "x" * len(digits_only)


def redact_sensitive_patterns(text: str) -> str:
    """
    Blankt IBAN- und Kartennummern-artige Muster, BEVOR Text an einen KI-Provider geht —
    auch an lokal betriebenes Ollama (siehe app/services/ai_extraction.py). Wirkt nur auf
    die an die KI gesendete Kopie, NIEMALS auf das gespeicherte Receipt.ocr_raw_text.
    Reine Funktion ohne DB-/Async-Abhängigkeit.
    """
    text = IBAN_PATTERN.sub(_mask_iban, text)
    text = CARD_PATTERN.sub(_mask_card, text)
    return text
