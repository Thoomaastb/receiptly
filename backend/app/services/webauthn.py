"""
WebAuthn/Passkey-Kernlogik — kapselt die vier py_webauthn-Kernmethoden (Security-Hardening
Phase 3, siehe concepts/security-hardening.md Abschnitt 4.3). Reine Funktionen ohne DB-/
Redis-Zugriff: Challenges speichert die aufrufende Route zwischen (app/auth/
webauthn_challenge.py), Credentials persistiert ebenfalls die Route (app/api/webauthn.py).

RP-ID/Origin kommen aus app/config.py (webauthn_rp_id_resolved/public_app_url) — beide
müssen zur tatsächlichen Browser-Domain passen, sonst schlagen alle Ceremonies fehl
(Deployment-Fallstrick, siehe Konzept).
"""

import hashlib
import hmac
import uuid

import webauthn
from webauthn.helpers.exceptions import WebAuthnException
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

from app.config import get_settings

settings = get_settings()


class WebauthnVerificationError(Exception):
    """
    Domänenspezifischer Fehler bei fehlgeschlagener Registrierungs-/Authentifizierungs-
    Verifikation (falsche Signatur, falscher Origin/RP-ID, kaputte/abgelaufene Challenge,
    ...) — kapselt py_webauthns diverse WebAuthnException-Subklassen, damit die aufrufende
    Route nur einen einzigen Fehlertyp in HTTP übersetzen muss (siehe CLAUDE.md: Services
    bleiben HTTP-agnostisch).
    """


def _rp_id() -> str:
    return settings.webauthn_rp_id_resolved


def generate_registration_options(
    *, user_id: uuid.UUID, username: str, exclude_credential_ids: list[str]
) -> tuple[str, bytes]:
    """
    Liefert (options_json_für_den_client, raw_challenge_bytes_zum_zwischenspeichern).
    `user_id` geht als rohe UUID-Bytes in den WebAuthn-User-Handle ein — der Handle
    identifiziert den User gegenüber dem Authenticator, nicht gegenüber unserer DB.
    `exclude_credential_ids` (bereits registrierte Credential-IDs des Users) verhindert,
    dass derselbe Authenticator doppelt registriert wird.
    """
    options = webauthn.generate_registration_options(
        rp_id=_rp_id(),
        rp_name=settings.webauthn_rp_name,
        user_id=user_id.bytes,
        user_name=username,
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.PREFERRED,
            user_verification=UserVerificationRequirement.PREFERRED,
        ),
        exclude_credentials=[
            PublicKeyCredentialDescriptor(id=webauthn.base64url_to_bytes(credential_id))
            for credential_id in exclude_credential_ids
        ],
    )
    return webauthn.options_to_json(options), options.challenge


def verify_registration(
    *, credential: str, expected_challenge: bytes
) -> tuple[str, bytes, int, str | None]:
    """
    Verifiziert den Browser-Response gegen die zuvor gespeicherte Challenge + erwarteten
    Origin/RP-ID. Liefert (credential_id_base64url, public_key_bytes, sign_count,
    transports) zum Speichern. `credential` ist das rohe JSON von
    `navigator.credentials.create()` als String — py_webauthn parst es selbst, kein
    eigenes Pydantic-Schema für das komplette WebAuthn-Response-Format nötig.

    `transports` kommt aus einem zweiten, separaten Parse-Durchlauf über dieselbe
    Credential-JSON, weil `VerifiedRegistration` dieses Feld nicht liefert —
    vernachlässigbarer Mehraufwand für ein seltenes, nutzerinitiiertes Ereignis.
    """
    try:
        result = webauthn.verify_registration_response(
            credential=credential,
            expected_challenge=expected_challenge,
            expected_rp_id=_rp_id(),
            expected_origin=settings.public_app_url,
        )
        parsed = webauthn.helpers.parse_registration_credential_json(credential)
    except WebAuthnException as exc:
        raise WebauthnVerificationError(str(exc)) from exc

    transports = parsed.response.transports
    transports_str = ",".join(t.value for t in transports) if transports else None

    return (
        webauthn.helpers.bytes_to_base64url(result.credential_id),
        result.credential_public_key,
        result.sign_count,
        transports_str,
    )


def credential_id_from_authentication_response(credential: str) -> str:
    """
    Liest die Credential-ID aus der rohen Authentication-Assertion-JSON, BEVOR die
    eigentliche kryptographische Verifikation läuft — die Route braucht sie vorab, um den
    passenden gespeicherten Credential-Datensatz (public_key/sign_count) nachzuschlagen.
    """
    try:
        parsed = webauthn.helpers.parse_authentication_credential_json(credential)
    except WebAuthnException as exc:
        raise WebauthnVerificationError(str(exc)) from exc
    return parsed.id


def generate_authentication_options(*, allow_credential_ids: list[str]) -> tuple[str, bytes]:
    """Liefert (options_json_für_den_client, raw_challenge_bytes_zum_zwischenspeichern)."""
    options = webauthn.generate_authentication_options(
        rp_id=_rp_id(),
        allow_credentials=[
            PublicKeyCredentialDescriptor(id=webauthn.base64url_to_bytes(credential_id))
            for credential_id in allow_credential_ids
        ],
    )
    return webauthn.options_to_json(options), options.challenge


def verify_authentication(
    *,
    credential: str,
    expected_challenge: bytes,
    credential_public_key: bytes,
    credential_current_sign_count: int,
) -> int:
    """Liefert den neuen sign_count zum Speichern. Wirft WebauthnVerificationError bei jedem Fehlschlag."""
    try:
        result = webauthn.verify_authentication_response(
            credential=credential,
            expected_challenge=expected_challenge,
            expected_rp_id=_rp_id(),
            expected_origin=settings.public_app_url,
            credential_public_key=credential_public_key,
            credential_current_sign_count=credential_current_sign_count,
        )
    except WebAuthnException as exc:
        raise WebauthnVerificationError(str(exc)) from exc

    return result.new_sign_count


def fake_allow_credential_ids(username: str) -> list[str]:
    """
    Deterministische Pseudo-Credential-ID für /authenticate/options bei unbekanntem
    Username ODER einem bekannten User ganz ohne registrierten Passkey (Enumeration-
    Schutz-Nachbesserung, Security-Review Phase 3). Ohne das wäre eine leere
    allow_credentials-Liste ein zuverlässiges "dieser Account existiert nicht"-Signal,
    weil normale User zur Passkey-Registrierung gezwungen sind (passkey_setup_required-
    Gate, app/api/auth.py) — praktisch jeder echte Account hat also mindestens einen
    Passkey, eine nicht-leere Liste würde die Existenz verraten.

    HMAC(session_secret, username) statt echtem Zufall: das Ergebnis muss für denselben
    Username bei jedem Aufruf identisch sein — sonst wäre schon die Instabilität selbst
    wieder ein Unterscheidungsmerkmal (die allow_credentials-Liste eines echten Accounts
    ändert sich zwischen zwei Aufrufen ja auch nicht). Kein Anspruch, dass die Fake-ID
    jemals mit einer echten Credential kollidiert — /authenticate/verify (app/api/
    webauthn.py::authenticate_verify) scheitert für sie zuverlässig am Lookup gegen
    webauthn_credentials, genau wie bei jeder anderen unbekannten Credential-ID, und
    liefert dieselbe generische 401-Fehlermeldung.

    session_secret statt encryption_key als HMAC-Key: session_secret ist bereits das
    Secret für den restlichen Login-/Session-Fluss (app/auth/session.py), während
    encryption_key ausschließlich zur Verschlüsselung ruhender Felddaten (TOTP-Secrets,
    KI-Provider-Keys) dient — andere Trust-Domäne, hier nicht passend. Eigener
    Domain-Separator im HMAC-Message statt Wiederverwendung des "receiptly-session"-Salts
    aus session.py, damit dieser Wert kryptographisch von Session-Tokens getrennt bleibt,
    obwohl er denselben Schlüssel nutzt.

    Ein einzelner Fake-Eintrag mit SHA-256-Digest-Länge (32 Bytes, base64url ~43 Zeichen)
    liegt in der für echte py_webauthn-Credential-IDs plausiblen Größenordnung.
    """
    digest = hmac.new(
        settings.session_secret.encode("utf-8"),
        b"webauthn-fake-credential:" + username.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return [webauthn.helpers.bytes_to_base64url(digest)]


def is_clone_suspected(*, stored_sign_count: int, new_sign_count: int) -> bool:
    """
    Clone-Detection-Sonderfall (Konzept 4.3): viele Platform-Authenticatoren (Touch ID,
    Face ID, Windows Hello) melden dauerhaft sign_count=0 statt hochzuzählen. Die Prüfung
    "neuer Wert muss größer als der gespeicherte sein" darf deshalb NUR greifen, wenn der
    neu gemeldete Wert tatsächlich > 0 UND kleiner als der gespeicherte Wert ist — sonst
    würden diese Authenticatoren nach dem ersten Login fälschlich als kompromittiert
    markiert und gesperrt.
    """
    return new_sign_count > 0 and new_sign_count < stored_sign_count
