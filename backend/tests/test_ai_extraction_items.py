"""
Reine Funktionstests für app/services/ai_extraction.py::_apply_items und
_parse_non_negative (kein DB-/Async-Fixture nötig, siehe test_receipt_heuristics.py).
_apply_items nimmt eine AsyncSession normalerweise nur für db.add() entgegen — dafür
reicht hier ein simples Fake-Objekt statt einer echten Session/DB-Fixture.
"""

import uuid

from app.services.ai_extraction import _apply_items, _none_if_zero, _parse_non_negative


class _FakeReceipt:
    def __init__(self):
        self.id = uuid.uuid4()


class _FakeSession:
    """Sammelt db.add()-Aufrufe, ohne eine echte DB-Verbindung zu benötigen."""

    def __init__(self):
        self.added: list = []

    def add(self, obj):
        self.added.append(obj)


def test_parse_non_negative_accepts_comma_decimal_string():
    assert _parse_non_negative("0,50") == 0.5


def test_parse_non_negative_rejects_negative_value():
    assert _parse_non_negative(-5) is None


def test_item_with_discount_amount_sets_field_and_keeps_net_total_price():
    db = _FakeSession()
    receipt = _FakeReceipt()
    items_data = [
        {
            "raw_name": "Wasser 6x1,5l",
            "quantity": 1,
            "unit_price": 4.99,
            "total_price": 3.99,
            "discount_amount": 1.0,
        }
    ]

    _apply_items(db, receipt, items_data)

    assert len(db.added) == 1
    item = db.added[0]
    assert item.discount_amount == 1.0
    assert item.total_price == 3.99


def test_item_without_discount_amount_stays_none():
    db = _FakeSession()
    receipt = _FakeReceipt()
    items_data = [
        {
            "raw_name": "Brot",
            "quantity": 1,
            "unit_price": 2.49,
            "total_price": 2.49,
            "discount_amount": None,
        }
    ]

    _apply_items(db, receipt, items_data)

    assert len(db.added) == 1
    assert db.added[0].discount_amount is None


def test_discount_amount_with_comma_decimal_string_is_parsed():
    db = _FakeSession()
    receipt = _FakeReceipt()
    items_data = [
        {
            "raw_name": "Joghurt",
            "quantity": 1,
            "unit_price": 1.0,
            "total_price": 0.5,
            "discount_amount": "0,50",
        }
    ]

    _apply_items(db, receipt, items_data)

    assert db.added[0].discount_amount == 0.5


def test_negative_discount_amount_becomes_none():
    db = _FakeSession()
    receipt = _FakeReceipt()
    items_data = [
        {
            "raw_name": "Kaese",
            "quantity": 1,
            "unit_price": 3.0,
            "total_price": 3.0,
            "discount_amount": -2,
        }
    ]

    _apply_items(db, receipt, items_data)

    assert db.added[0].discount_amount is None


def test_zero_discount_amount_from_ai_is_normalized_to_none():
    """KI liefert trotz Prompt-Anweisung "sonst null" öfter 0 statt null, wenn kein
    Rabatt vorliegt — 0.0 hier wie None behandeln, sonst zeigt das Frontend fälschlich
    "Rabatt -0.00" bei jedem Artikel an (live per Screenshot bestätigter Bug)."""
    db = _FakeSession()
    receipt = _FakeReceipt()
    items_data = [
        {
            "raw_name": "Milch",
            "quantity": 1,
            "unit_price": 1.19,
            "total_price": 1.19,
            "discount_amount": 0,
        }
    ]

    _apply_items(db, receipt, items_data)

    assert db.added[0].discount_amount is None


def test_none_if_zero_normalizes_only_exact_zero():
    assert _none_if_zero(0) is None
    assert _none_if_zero(0.0) is None
    assert _none_if_zero(None) is None
    assert _none_if_zero(1.0) == 1.0
