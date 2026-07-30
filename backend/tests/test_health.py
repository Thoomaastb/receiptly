"""
Reine Funktionstests für app/api/health.py::_is_newer()/_same_version() (siehe
test_pii_redaction.py für das Muster) — kein DB-/Async-Fixture nötig, da diese Funktionen
reine Tupel-/String-Vergleiche ohne Seiteneffekte sind.
"""

from app.api.health import _is_newer, _is_stable, _same_version


def test_newer_tag_with_v_prefix_is_detected():
    assert _is_newer("v0.45.0", "0.44.0") is True


def test_older_tag_with_v_prefix_is_not_newer():
    assert _is_newer("v0.44.0", "0.45.0") is False


def test_same_version_is_not_newer():
    assert _is_newer("v0.45.0", "0.45.0") is False


def test_unparsable_tag_falls_back_to_not_newer_instead_of_crashing():
    assert _is_newer("garbage", "0.45.0") is False


def test_prerelease_suffix_does_not_falsely_look_newer():
    # Regressionstest für den 2026-07-30 gemeldeten Bug: eine laufende Pre-Release durfte
    # nicht mehr fälschlich als "uralt" (0,0,0) gegen einen älteren Stable-Tag erscheinen.
    assert _is_newer("v0.49.5", "0.49.6-rc.1") is False


def test_prerelease_suffix_base_version_compares_correctly():
    assert _is_newer("v0.49.7", "0.49.6-rc.1") is True


def test_short_version_string_is_padded_before_comparison():
    assert _is_newer("v0.45.0", "0.45") is False


def test_same_version_with_different_prerelease_suffix_is_not_same():
    assert _same_version("0.49.6-rc.2", "0.49.6-rc.1") is False


def test_same_version_ignores_v_prefix():
    assert _same_version("v0.49.6", "0.49.6") is True


def test_is_stable_detects_prerelease_suffix():
    assert _is_stable("0.49.6-rc.1") is False
    assert _is_stable("0.49.6") is True
