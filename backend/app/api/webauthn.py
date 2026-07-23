"""
Passkey-/WebAuthn-Endpoints (Security-Hardening Phase 3, siehe
concepts/security-hardening.md Abschnitt 4.3). Zwei klar getrennte Endpoint-Gruppen:

- Registrierung + Verwaltung (register/*, credentials/*) braucht eine bestehende Session
  (get_current_user) — ein User verwaltet nur seine eigenen Passkeys.
- Login (authenticate/*) hat bewusst KEINE get_current_user-Abhängigkeit — das ist der
  Sinn dieser Endpoints, hier startet die Authentifizierung erst.

`_finalize_first_factor` wird aus app/api/auth.py importiert (siehe dortiger Docstring) —
bewusst geteilte Logik statt Duplikation, damit ein Passkey-Login exakt dieselbe
Admin/TOTP-Pflicht-Verzweigung durchläuft wie der Passwort-Login.
"""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import _finalize_first_factor
from app.auth.dependencies import get_current_user
from app.auth.rate_limit import check_rate_limit, rate_limit
from app.auth.request_meta import get_client_ip
from app.auth.webauthn_challenge import (
    pop_authentication_challenge,
    pop_registration_challenge,
    store_authentication_challenge,
    store_registration_challenge,
)
from app.database import get_db
from app.models.user import User
from app.models.webauthn_credential import WebauthnCredential
from app.schemas.account import RequiresReactivationResponse
from app.schemas.auth import RequiresTotpResponse, UserResponse
from app.schemas.webauthn import (
    WebauthnAuthenticateOptionsRequest,
    WebauthnAuthenticateOptionsResponse,
    WebauthnAuthenticateVerifyRequest,
    WebauthnCredentialRename,
    WebauthnCredentialResponse,
    WebauthnRegisterOptionsResponse,
    WebauthnRegisterVerifyRequest,
)
from app.services import webauthn as webauthn_service
from app.services.audit import record_event
from app.services.household_security import get_or_create_security_settings, lock_household_security

router = APIRouter(prefix="/webauthn", tags=["webauthn"])


def _generic_login_error() -> HTTPException:
    """
    Generische Fehlermeldung für /authenticate/verify — bewusst identisch für "unbekannter
    Username bei /authenticate/options", "Credential nicht gefunden" und "kryptographische
    Verifikation fehlgeschlagen" (Enumeration-Schutz, analog zum Passwort-Login in
    app/api/auth.py::login()). Eine Factory statt einer geteilten Modul-Konstante, weil
    ein einzelnes HTTPException-Objekt bei parallelen Requests nicht sicher mehrfach
    ge-raised werden sollte (Traceback-Zuweisung ist nicht auf ein geteiltes
    Exception-Objekt ausgelegt).
    """
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Ungültige Anmeldedaten")


async def _get_own_credential(db: AsyncSession, credential_id: uuid.UUID, user: User) -> WebauthnCredential:
    result = await db.execute(
        select(WebauthnCredential).where(
            WebauthnCredential.id == credential_id, WebauthnCredential.user_id == user.id
        )
    )
    credential = result.scalar_one_or_none()
    if credential is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Passkey nicht gefunden")
    return credential


@router.post("/register/options", response_model=WebauthnRegisterOptionsResponse)
async def register_options(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> WebauthnRegisterOptionsResponse:
    """
    `exclude_credentials` verhindert, dass derselbe Authenticator (z.B. dieselbe Touch-ID-
    Instanz) doppelt registriert wird. Ein erneuter Aufruf überschreibt eine noch offene
    vorherige Challenge desselben Users (siehe app/auth/webauthn_challenge.py).
    """
    result = await db.execute(
        select(WebauthnCredential.credential_id).where(WebauthnCredential.user_id == user.id)
    )
    exclude_credential_ids = [row[0] for row in result.all()]

    options_json, challenge = webauthn_service.generate_registration_options(
        user_id=user.id, username=user.username, exclude_credential_ids=exclude_credential_ids
    )
    await store_registration_challenge(user.id, challenge)
    return WebauthnRegisterOptionsResponse(options=options_json)


@router.post(
    "/register/verify",
    response_model=WebauthnCredentialResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register_verify(
    payload: WebauthnRegisterVerifyRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WebauthnCredential:
    challenge = await pop_registration_challenge(user.id)
    if challenge is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Keine offene Registrierung — zuerst /webauthn/register/options aufrufen.",
        )

    try:
        credential_id, public_key, sign_count, transports = webauthn_service.verify_registration(
            credential=payload.credential, expected_challenge=challenge
        )
    except webauthn_service.WebauthnVerificationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Passkey-Registrierung fehlgeschlagen"
        ) from exc

    credential = WebauthnCredential(
        user_id=user.id,
        credential_id=credential_id,
        public_key=public_key,
        sign_count=sign_count,
        transports=transports,
        device_label=payload.device_label,
    )
    db.add(credential)
    try:
        await db.flush()
    except IntegrityError as exc:
        # credential_id ist global unique (siehe Migration 0016) — theoretisch möglich,
        # wenn derselbe physische Authenticator bei einem anderen User bereits registriert
        # ist (exclude_credentials in /register/options deckt nur den eigenen User ab).
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Dieser Passkey ist bereits registriert."
        ) from exc

    await record_event(
        db,
        household_id=user.household_id,
        user_id=user.id,
        event_type="passkey_registered",
        request=request,
        metadata={"credential_id": str(credential.id), "device_label": payload.device_label},
    )
    return credential


@router.get("/credentials", response_model=list[WebauthnCredentialResponse])
async def list_credentials(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> list[WebauthnCredential]:
    """Nie public_key/credential_id roh exponieren — WebauthnCredentialResponse filtert das bereits aus."""
    result = await db.execute(
        select(WebauthnCredential)
        .where(WebauthnCredential.user_id == user.id)
        .order_by(WebauthnCredential.created_at.asc())
    )
    return list(result.scalars().all())


@router.patch("/credentials/{credential_id}", response_model=WebauthnCredentialResponse)
async def rename_credential(
    credential_id: uuid.UUID,
    payload: WebauthnCredentialRename,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WebauthnCredential:
    credential = await _get_own_credential(db, credential_id, user)
    credential.device_label = payload.device_label
    await db.commit()
    await db.refresh(credential)
    return credential


@router.delete("/credentials/{credential_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_credential(
    credential_id: uuid.UUID,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Schutz vor "letzter Passkey wird gelöscht" (Security-Hardening Phase 4, Konzept 4.1):
    solange der haushaltsweite Passkey-Exklusiv-Login aktiv ist, lehnt das Löschen der
    letzten verbleibenden Credential des Users mit 409 ab — sonst würde sich der User
    selbst aussperren, ohne dass das Precondition-Gate beim Aktivieren des Schalters das
    hätte verhindern können (das prüft nur den Zustand zum Aktivierungszeitpunkt, nicht
    danach). Ohne aktiven Schalter bleibt das Löschen des letzten Passkeys weiterhin
    uneingeschränkt möglich — Passwort (+ ggf. TOTP) bleibt dann ein vollwertiger Rückweg.

    lock_household_security() muss vor der Zählung stehen (Security-Review Phase 4, M1):
    sonst lesen zwei parallele Löschungen der letzten zwei Passkeys beide noch "2 Stück"
    unter READ COMMITTED, bevor die jeweils andere committet, und beide löschen durch.
    """
    await lock_household_security(db, user.household_id)
    credential = await _get_own_credential(db, credential_id, user)

    security_settings = await get_or_create_security_settings(db, user.household_id)
    if security_settings.passkey_exclusive_login:
        remaining_result = await db.execute(
            select(func.count())
            .select_from(WebauthnCredential)
            .where(WebauthnCredential.user_id == user.id)
        )
        if remaining_result.scalar_one() <= 1:
            # Bewusste Ergänzung über den Auftrags-Wortlaut hinaus (dort nur "409
            # ablehnen" gefordert): ein Audit-Event, weil ein abgelehnter Löschversuch des
            # letzten Passkeys bei aktivem Exklusiv-Modus dasselbe sicherheitsrelevante
            # Gewicht hat wie die anderen bereits auditierten Passkey-Events in dieser Datei.
            await record_event(
                db,
                household_id=user.household_id,
                user_id=user.id,
                event_type="passkey_delete_blocked",
                request=request,
                metadata={"credential_id": str(credential_id), "reason": "passkey_exclusive_login"},
            )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Letzter Passkey kann nicht gelöscht werden, solange der exklusive "
                    "Passkey-Login aktiv ist."
                ),
            )

    await db.delete(credential)
    await record_event(
        db,
        household_id=user.household_id,
        user_id=user.id,
        event_type="passkey_removed",
        request=request,
        metadata={"credential_id": str(credential_id)},
    )


@router.post(
    "/authenticate/options",
    response_model=WebauthnAuthenticateOptionsResponse,
    dependencies=[
        Depends(rate_limit("webauthn_authenticate_options_ip", limit=20, window_seconds=900))
    ],
)
async def authenticate_options(
    payload: WebauthnAuthenticateOptionsRequest, request: Request, db: AsyncSession = Depends(get_db)
) -> WebauthnAuthenticateOptionsResponse:
    """
    Öffentlich (kein get_current_user — hier beginnt der Login). Identifiziert den User
    wie beim Passwort-Login per Username ODER E-Mail (app/api/auth.py::login()) und lädt
    dessen registrierte Credential-IDs für `allow_credentials`.

    Zwei Rate-Limits wie beim Passwort-Login (app/api/auth.py::login()): das IP-only-Limit
    (20/15min, `Depends()`, Schutz gegen das Durchprobieren vieler Usernames von einer IP)
    läuft vor, das IP+Username-Limit (10/15min) direkt im Body, weil `payload.username`
    erst nach dessen Auflösung verfügbar ist — gleicher Grund wie dort.

    Enumeration-Schutz: bleiben `allow_credential_ids` leer — unbekannter Username ODER
    ein bekannter User ganz ohne registrierten Passkey —, wird die Liste durch eine
    deterministische Fake-Credential-ID ersetzt (webauthn_service.fake_allow_credential_ids,
    siehe dort für die Begründung). Ohne das würde eine nicht-leere vs. leere Liste
    zuverlässig verraten, ob der Account existiert, weil normale User zur Passkey-
    Registrierung gezwungen sind (passkey_setup_required-Gate) — praktisch jeder echte
    Account hat also mindestens einen Passkey. Bei unbekanntem Username wird die Challenge
    zusätzlich unter einer zufälligen, KEINEM echten User zugeordneten Platzhalter-ID
    gespeichert — /authenticate/verify kann darüber (wie auch über die Fake-Credential-ID
    selbst) nie einen echten Credential-Datensatz auflösen und liefert dieselbe generische
    Fehlermeldung wie ein tatsächlicher Verifikationsfehler.
    """
    ip = get_client_ip(request)
    await check_rate_limit(
        "webauthn_authenticate_options_ip_username", f"{ip}:{payload.username}", 10, 900
    )

    result = await db.execute(
        select(User).where((User.username == payload.username) | (User.email == payload.username))
    )
    user = result.scalar_one_or_none()

    allow_credential_ids: list[str] = []
    if user is not None:
        creds = await db.execute(
            select(WebauthnCredential.credential_id).where(WebauthnCredential.user_id == user.id)
        )
        allow_credential_ids = [row[0] for row in creds.all()]

    if not allow_credential_ids:
        allow_credential_ids = webauthn_service.fake_allow_credential_ids(payload.username)

    options_json, challenge = webauthn_service.generate_authentication_options(
        allow_credential_ids=allow_credential_ids
    )
    options_id = await store_authentication_challenge(
        user.id if user is not None else uuid.uuid4(), challenge
    )
    return WebauthnAuthenticateOptionsResponse(options=options_json, options_id=options_id)


@router.post(
    "/authenticate/verify",
    response_model=UserResponse | RequiresTotpResponse | RequiresReactivationResponse,
    dependencies=[Depends(rate_limit("webauthn_authenticate_verify_ip", limit=15, window_seconds=900))],
)
async def authenticate_verify(
    payload: WebauthnAuthenticateVerifyRequest,
    response: Response,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> UserResponse | RequiresTotpResponse | RequiresReactivationResponse:
    """
    Zweiter Schritt des Passkey-Logins (siehe authenticate_options oben). Bei Erfolg
    durchläuft der User dieselbe Admin/TOTP-Verzweigung wie der Passwort-Login
    (_finalize_first_factor, app/api/auth.py) — der Passkey ersetzt für Admins nur den
    Passwort-Schritt, die TOTP-Pflicht bleibt bestehen (Konzept 4.1).
    """
    popped = await pop_authentication_challenge(payload.options_id)
    if popped is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Anmeldung abgelaufen oder ungültig — bitte erneut versuchen.",
        )
    expected_user_id, challenge = popped

    try:
        credential_id = webauthn_service.credential_id_from_authentication_response(payload.credential)
    except webauthn_service.WebauthnVerificationError as exc:
        raise _generic_login_error() from exc

    result = await db.execute(
        select(WebauthnCredential).where(
            WebauthnCredential.credential_id == credential_id,
            WebauthnCredential.user_id == expected_user_id,
        )
    )
    stored_credential = result.scalar_one_or_none()

    user: User | None = None
    if stored_credential is not None:
        user_result = await db.execute(select(User).where(User.id == stored_credential.user_id))
        user = user_result.scalar_one_or_none()

    if stored_credential is None or user is None:
        # Kein audit_log-Eintrag möglich (kein bekannter Haushalt) — analog zum
        # unbekannten Username beim Passwort-Login.
        raise _generic_login_error()

    try:
        new_sign_count = webauthn_service.verify_authentication(
            credential=payload.credential,
            expected_challenge=challenge,
            credential_public_key=stored_credential.public_key,
            credential_current_sign_count=stored_credential.sign_count,
        )
    except webauthn_service.WebauthnVerificationError as exc:
        await record_event(
            db,
            household_id=user.household_id,
            user_id=user.id,
            event_type="passkey_login_failed",
            request=request,
        )
        raise _generic_login_error() from exc

    if webauthn_service.is_clone_suspected(
        stored_sign_count=stored_credential.sign_count, new_sign_count=new_sign_count
    ):
        # Sign_count bewusst NICHT übernommen — würde die Zähler-Historie des
        # möglicherweise geklonten Authenticators fortschreiben.
        await record_event(
            db,
            household_id=user.household_id,
            user_id=user.id,
            event_type="passkey_login_failed",
            request=request,
            metadata={"reason": "clone_suspected", "credential_db_id": str(stored_credential.id)},
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Passkey abgelehnt — möglicher Klon erkannt.",
        )

    stored_credential.sign_count = new_sign_count
    stored_credential.last_used_at = datetime.now(UTC)

    return await _finalize_first_factor(
        db, user, response, request, success_event_type="passkey_login_success"
    )
