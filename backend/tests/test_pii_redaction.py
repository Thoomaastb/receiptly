"""
Erster Test im Backend (siehe app/services/pii_redaction.py — reine Funktion, keine
DB-/Async-Abhängigkeit nötig). Prüft, dass IBAN- und Kartennummern-artige Muster
zuverlässig geblankt werden, BEVOR Text an einen KI-Provider geht.
"""

from app.services.pii_redaction import redact_sensitive_patterns


def test_iban_with_spaces_is_masked():
    text = "Zahlung per Überweisung auf DE44 1234 5678 9012 3456 bitte."
    redacted = redact_sensitive_patterns(text)

    assert "1234 5678 9012 3456" not in redacted
    assert "DExx xxxx xxxx xxxx xxxx" in redacted
    # Rest des Satzes bleibt unangetastet
    assert "Zahlung per Überweisung auf" in redacted
    assert "bitte." in redacted


def test_iban_without_spaces_is_masked():
    text = "IBAN: DE441234567890123456"
    redacted = redact_sensitive_patterns(text)

    assert "1234567890123456" not in redacted
    assert "DExx xxxx xxxx xxxx xxxx" in redacted


def test_real_world_iban_grouping_partial_remainder_is_a_known_limitation():
    # Reale IBAN-Formatierung gruppiert in 4er-Blöcken mit einem kürzeren Restblock (hier
    # "00", 2 Stellen) — die Regel verlangt exakt 4-stellige Blöcke, der Restblock wird
    # daher NICHT erfasst. Bewusst dokumentiertes False-Negative-Risiko (siehe Plan/
    # Security-Review), kein Bug: die ersten Blöcke (die sensiblen Ziffern) sind trotzdem weg.
    text = "DE89 3704 0044 0532 0130 00"
    redacted = redact_sensitive_patterns(text)

    assert "3704 0044 0532 0130" not in redacted
    assert "DExx xxxx xxxx xxxx xxxx" in redacted


def test_card_number_with_spaces_is_masked():
    text = "Karte: 4111 1111 1111 1111 belastet."
    redacted = redact_sensitive_patterns(text)

    assert "4111 1111 1111 1111" not in redacted
    assert "xxxxxxxxxxxxxxxx" in redacted  # 16 Ziffern -> 16 x


def test_card_number_with_hyphens_is_masked():
    text = "4111-1111-1111-1111"
    redacted = redact_sensitive_patterns(text)

    assert redacted == "x" * 16


def test_short_numeric_sequence_is_not_touched():
    # Bon-/Belegnummern u.ä. mit < 13 Ziffern sind keine Kartennummern und bleiben stehen.
    text = "Bon-Nr. 4711 - Danke für Ihren Einkauf"
    redacted = redact_sensitive_patterns(text)

    assert redacted == text


def test_combined_receipt_text_masks_both_patterns_and_keeps_rest():
    text = (
        "REWE Markt GmbH\n"
        "Datum: 12.03.2025\n"
        "IBAN DE44 1234 5678 9012 3456 fuer Rueckerstattung\n"
        "Kartenzahlung 4111 1111 1111 1111\n"
        "Gesamt: 23,45 EUR"
    )
    redacted = redact_sensitive_patterns(text)

    assert "DE44 1234 5678 9012 3456" not in redacted
    assert "4111 1111 1111 1111" not in redacted
    assert "REWE Markt GmbH" in redacted
    assert "Gesamt: 23,45 EUR" in redacted
