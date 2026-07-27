"""
Reine Funktionstests für app/services/receipt_heuristics.py (kein DB-/Async-Fixture nötig,
siehe test_pii_redaction.py). Deckt Datum-, Betrags- und Währungs-Heuristik ab, inkl.
Fällen, in denen bewusst None statt eines geratenen Werts zurückkommen soll.
"""

from datetime import date

from app.services.receipt_heuristics import extract_receipt_heuristics


def test_none_input_returns_all_none():
    result = extract_receipt_heuristics(None)

    assert result.receipt_date is None
    assert result.total_amount is None
    assert result.currency is None


def test_good_date_with_four_digit_year_is_parsed():
    text = "REWE Markt GmbH\nDatum: 12.03.2025\nGesamt: 23,45 EUR"
    result = extract_receipt_heuristics(text)

    assert result.receipt_date == date(2025, 3, 12)


def test_two_digit_year_is_expanded_to_20yy():
    text = "Kassenbon 25-12-25"
    result = extract_receipt_heuristics(text)

    assert result.receipt_date == date(2025, 12, 25)


def test_implausible_date_candidate_is_skipped_in_favor_of_next_match():
    # "32.13.2025" ist syntaktisch kein gültiges Datum (Tag > 31 wäre ok hier, aber Monat >
    # 12 nicht) - erster Treffer scheitert an der Monatsgrenze, der zweite ist valide.
    text = "Ref-Nr. 32.13.2025 - eigentliches Datum: 05.01.2025"
    result = extract_receipt_heuristics(text)

    assert result.receipt_date == date(2025, 1, 5)


def test_future_date_is_rejected():
    text = "Datum: 01.01.2099"
    result = extract_receipt_heuristics(text)

    assert result.receipt_date is None


def test_amount_line_with_summe_keyword_is_extracted():
    text = "Artikel 1,99\nSumme: 12,34 EUR"
    result = extract_receipt_heuristics(text)

    assert result.total_amount == 12.34


def test_amount_line_with_thousands_separator_is_parsed():
    text = "Gesamtbetrag: 1.234,56 EUR"
    result = extract_receipt_heuristics(text)

    assert result.total_amount == 1234.56


def test_amount_without_keyword_line_returns_none():
    # Keine Zeile mit Summe/Total/Gesamt/Zu zahlen/Betrag - bewusst kein "größte Zahl
    # im Text"-Fallback, lieber None als raten.
    text = "Milch 1,99\nBrot 2,49\nEier 3,29"
    result = extract_receipt_heuristics(text)

    assert result.total_amount is None


def test_euro_symbol_present_yields_eur():
    result = extract_receipt_heuristics("Gesamt: 9,99 €")

    assert result.currency == "EUR"


def test_eur_code_without_symbol_yields_eur():
    result = extract_receipt_heuristics("Gesamt: 9,99 EUR")

    assert result.currency == "EUR"


def test_no_currency_hint_yields_none():
    result = extract_receipt_heuristics("Gesamt: 9,99")

    assert result.currency is None
