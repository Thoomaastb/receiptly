"""
Konto-Löschung (DSGVO Art. 17, siehe concepts/konto-loeschen-datenexport.md 3.2/3.3) —
geteilte Logik zwischen Stufe A (Löschantrag, app/api/account.py) und Stufe B
(Scheduler-Teardown, app/scripts/account_deletion_teardown.py). Domänenspezifische
Exceptions statt HTTPException tief in der Logik (siehe CLAUDE.md) — nur
`verify_active_login_factor` wirft direkt HTTPException, weil sie 1:1 das bestehende
Re-Auth-Muster aus app/api/totp.py::_reverify() spiegelt (dort ebenso).
"""

from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, Request, Response, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import webauthn_challenge
from app.auth.pending_reactivation import create_pending_reactivation
from app.auth.security import verify_password
from app.models.user import User, UserRole
from app.models.webauthn_credential import WebauthnCredential
from app.schemas.account import AccountDeletionRequest, RequiresReactivationResponse
from app.services import totp
from app.services import webauthn as webauthn_service
from app.services.audit import record_event
from app.services.crypto import decrypt_secret
from app.services.household_security import get_or_create_security_settings, lock_household_security

_DELETION_GRACE_PERIOD_DAYS = 14


class AdminGateBlockedError(Exception):
    """User ist einziger ADMIN, weitere nicht-Platzhalter Haushaltsmitglieder existieren noch."""


async def check_admin_gate(db: AsyncSession, user: User) -> None:
    """
    Gate aus Konzept 3.2/Q5: ein admin-loser Haushalt ist ein kaputter Zustand — blockiert
    nur, wenn der User ADMIN ist, keine weiteren (nicht-Platzhalter) Admins existieren UND
    weitere (nicht-Platzhalter) Mitglieder da sind, für die dieser Zustand relevant wäre.
    Wird sowohl von request_deletion() (Stufe A) als auch erneut vom Scheduler-Teardown
    (Stufe B, Rollen könnten sich in der Karenzzeit geändert haben) aufgerufen.
    """
    if user.role != UserRole.ADMIN:
        return

    other_admins = await db.execute(
        select(func.count())
        .select_from(User)
        .where(
            User.household_id == user.household_id,
            User.id != user.id,
            User.role == UserRole.ADMIN,
            User.is_placeholder.is_(False),
        )
    )
    if other_admins.scalar_one() > 0:
        return

    other_members = await db.execute(
        select(func.count())
        .select_from(User)
        .where(
            User.household_id == user.household_id,
            User.id != user.id,
            User.is_placeholder.is_(False),
        )
    )
    if other_members.scalar_one() > 0:
        raise AdminGateBlockedError()


async def request_deletion(
    db: AsyncSession, user: User, request: Request | None = None
) -> None:
    """
    Stufe A (Konzept 3.2): Advisory-Lock gegen TOCTOU mit einer gleichzeitigen
    Rollenänderung (lock_household_security() — derselbe Baustein wie
    Security-Hardening Phase 4), Gate-Check, setzt scheduled_deletion_at auf jetzt + 14
    Tage. KEINE Session-Invalidierung hier — die Response muss im aufrufenden Endpoint
    noch aus der aktuellen (bis dahin gültigen) Session gebaut werden, erst danach
    invalidiert der Endpoint alle Sessions (siehe app/api/account.py).
    """
    await lock_household_security(db, user.household_id)
    await check_admin_gate(db, user)

    user.scheduled_deletion_at = datetime.now(UTC) + timedelta(days=_DELETION_GRACE_PERIOD_DAYS)
    await record_event(
        db,
        household_id=user.household_id,
        user_id=user.id,
        event_type="account_deletion_requested",
        request=request,
    )


async def _verify_passkey_factor(
    db: AsyncSession, user: User, payload: AccountDeletionRequest
) -> None:
    """
    Passkey-Bestätigung bei aktivem passkey_exclusive_login — anders als der normale
    Passkey-LOGIN (app/api/webauthn.py::authenticate_verify) ist der User hier bereits
    über eine Session bekannt: kein Username-Lookup, die Prüfung läuft ausschließlich
    gegen die eigenen WebauthnCredential-Zeilen dieses Users.
    """
    if payload.passkey_credential is None or payload.passkey_options_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Passkey-Bestätigung erforderlich"
        )

    popped = await webauthn_challenge.pop_authentication_challenge(payload.passkey_options_id)
    if popped is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Passkey-Bestätigung abgelaufen oder ungültig — bitte erneut versuchen.",
        )
    expected_user_id, challenge = popped
    if expected_user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Passkey-Verifikation fehlgeschlagen"
        )

    try:
        credential_id = webauthn_service.credential_id_from_authentication_response(
            payload.passkey_credential
        )
    except webauthn_service.WebauthnVerificationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Passkey-Verifikation fehlgeschlagen"
        ) from exc

    result = await db.execute(
        select(WebauthnCredential).where(
            WebauthnCredential.credential_id == credential_id,
            WebauthnCredential.user_id == user.id,
        )
    )
    stored_credential = result.scalar_one_or_none()
    if stored_credential is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Passkey-Verifikation fehlgeschlagen"
        )

    try:
        new_sign_count = webauthn_service.verify_authentication(
            credential=payload.passkey_credential,
            expected_challenge=challenge,
            credential_public_key=stored_credential.public_key,
            credential_current_sign_count=stored_credential.sign_count,
        )
    except webauthn_service.WebauthnVerificationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Passkey-Verifikation fehlgeschlagen"
        ) from exc

    stored_credential.sign_count = new_sign_count
    stored_credential.last_used_at = datetime.now(UTC)


async def verify_active_login_factor(
    db: AsyncSession, user: User, payload: AccountDeletionRequest
) -> None:
    """
    Re-Auth vor dem Löschantrag (Konzept Q11/3.3) — Reeingabe des jeweils AKTIVEN
    Login-Faktors: Passwort im Normalfall, Passkey-Bestätigung, falls der haushaltsweite
    Passkey-Exklusiv-Login aktiv ist. Zusätzlich TOTP, falls für den User aktiv. Wirft
    HTTPException(400) mit spezifischem detail je fehlendem/falschem Faktor — Muster
    analog zu app/api/totp.py::_reverify().
    """
    security_settings = await get_or_create_security_settings(db, user.household_id)

    if security_settings.passkey_exclusive_login:
        await _verify_passkey_factor(db, user, payload)
    else:
        if payload.current_password is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Passwort erforderlich"
            )
        if not verify_password(payload.current_password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Passwort ist falsch"
            )

    if user.totp_enabled:
        if not payload.totp_code:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="TOTP-Code erforderlich"
            )
        secret: str | None = None
        if user.totp_secret:
            try:
                secret = decrypt_secret(user.totp_secret)
            except ValueError:
                # ENCRYPTION_KEY wurde rotiert oder das Secret ist anderweitig nicht mehr
                # entschlüsselbar — wie ein falscher Code behandeln (siehe app/api/auth.py
                # ::login_with_totp() für dasselbe Muster), nicht als 500 durchschlagen lassen.
                secret = None
        if secret is None or not totp.verify_code(secret, payload.totp_code):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Ungültiger TOTP-Code"
            )


async def check_reactivation_required(
    db: AsyncSession, user: User, response: Response, request: Request
) -> RequiresReactivationResponse | None:
    """
    Login-Hook (siehe app/api/auth.py::_finalize_first_factor()/login_with_totp()): fängt
    einen ansonsten vollständig authentifizierten Login-Versuch während der 14-tägigen
    Löschungs-Karenzzeit ab, statt eine normale Session zu erstellen — legt stattdessen
    einen Pending-Reactivation-State an (app/auth/pending_reactivation.py) und gibt dem
    Frontend die Möglichkeit, POST /account/reactivate anzubieten.
    """
    if user.scheduled_deletion_at is None:
        return None

    await create_pending_reactivation(user.id, response, request)
    return RequiresReactivationResponse(scheduled_deletion_at=user.scheduled_deletion_at)
