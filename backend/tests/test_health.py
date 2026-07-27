"""
Reine Funktionstests für app/api/health.py::_is_newer() (siehe test_pii_redaction.py für
das Muster) — kein DB-/Async-Fixture nötig, da _is_newer() ein reiner Semver-Tupel-
Vergleich ohne Seiteneffekte ist.
"""

from app.api.health import _is_newer


def test_newer_tag_with_v_prefix_is_detected():
    assert _is_newer("v0.45.0", "0.44.0") is True


def test_older_tag_with_v_prefix_is_not_newer():
    assert _is_newer("v0.44.0", "0.45.0") is False


def test_same_version_is_not_newer():
    assert _is_newer("v0.45.0", "0.45.0") is False


def test_unparsable_tag_falls_back_to_not_newer_instead_of_crashing():
    assert _is_newer("garbage", "0.45.0") is False
