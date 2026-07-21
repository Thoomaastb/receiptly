"""
TOTP-Kernlogik (Secret-Erzeugung, QR-SVG, Verifikation, Recovery-Codes) — siehe
concepts/security-hardening.md Abschnitt 4.2. Reine Funktionen ohne DB-/Redis-Zugriff:
Secrets werden hier nie persistiert, das übernimmt die aufrufende Route (Fernet-
Verschlüsselung über app/services/crypto.py vor dem Speichern in users.totp_secret).
"""

import io
import secrets

import pyotp
import qrcode
import qrcode.image.svg

from app.auth.security import hash_password, verify_password

_ISSUER_NAME = "receiptly"
_RECOVERY_CODE_COUNT = 8
_RECOVERY_CODE_GROUP_LENGTH = 5
# Ohne 0/O/1/I/L — Verwechslungsgefahr beim Abtippen eines handschriftlich notierten Codes.
_RECOVERY_CODE_ALPHABET = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"


def generate_secret() -> str:
    """Base32-Klartext-Secret — Aufrufer verschlüsselt vor dem Speichern selbst (Fernet)."""
    return pyotp.random_base32()


def provisioning_uri(secret: str, account_name: str) -> str:
    return pyotp.totp.TOTP(secret).provisioning_uri(name=account_name, issuer_name=_ISSUER_NAME)


def generate_qr_svg(secret: str, account_name: str) -> str:
    """
    Serverseitig gerendertes SVG-Markup (kein CDN/externer QR-Dienst — DSGVO-Prinzip,
    Backend hat das Secret ohnehin). Gibt das vollständige `<svg>...</svg>`-Dokument als
    String zurück, für `{@html}` im Frontend, ausschließlich aus dieser eigenen Antwort.
    """
    uri = provisioning_uri(secret, account_name)
    img = qrcode.make(uri, image_factory=qrcode.image.svg.SvgPathImage)
    buffer = io.BytesIO()
    img.save(buffer)
    return buffer.getvalue().decode("utf-8")


def verify_code(secret: str, code: str) -> bool:
    """±1 Zeitschritt Toleranz (~30s Drift), wie im Konzept entschieden (Abschnitt 4.2)."""
    return pyotp.TOTP(secret).verify(code, valid_window=1)


def generate_recovery_codes(count: int = _RECOVERY_CODE_COUNT) -> list[str]:
    """
    Kryptographisch zufällige, menschenlesbar formatierte Einmal-Codes (z.B. "7K9P4-XM3RQ").
    Nur für die einmalige Klartext-Anzeige im Response gedacht — vor dem Speichern über
    `hash_recovery_code()` hashen, niemals im Klartext persistieren.
    """
    codes = []
    for _ in range(count):
        raw = "".join(
            secrets.choice(_RECOVERY_CODE_ALPHABET)
            for _ in range(_RECOVERY_CODE_GROUP_LENGTH * 2)
        )
        codes.append(f"{raw[:_RECOVERY_CODE_GROUP_LENGTH]}-{raw[_RECOVERY_CODE_GROUP_LENGTH:]}")
    return codes


def _normalize_recovery_code(code: str) -> str:
    """Trennzeichen/Groß-Kleinschreibung sind reine Anzeigeformatierung, nicht Teil des Secrets."""
    return code.strip().upper().replace("-", "").replace(" ", "")


def hash_recovery_code(code: str) -> str:
    """Argon2id wie Passwörter (app/auth/security.py) — keine zweite Hash-Implementierung."""
    return hash_password(_normalize_recovery_code(code))


def verify_recovery_code(code: str, code_hash: str) -> bool:
    return verify_password(_normalize_recovery_code(code), code_hash)
