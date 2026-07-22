import logging
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import (
    get_current_raw_session_token,
    get_current_user,
    require_admin,
    require_totp_enrolled,
)
from app.auth.password_reset import consume_reset_token, create_reset_token
from app.auth.pending_2fa import (
    PENDING_2FA_COOKIE_NAME,
    create_pending_2fa,
    destroy_pending_2fa,
    get_pending_user_id,
    register_failed_attempt,
)
from app.auth.rate_limit import check_rate_limit, rate_limit
from app.auth.request_meta import get_client_ip
from app.auth.security import hash_password, verify_password
from app.auth.session import (
    create_session,
    destroy_session,
    get_user_id_by_raw_token,
    invalidate_other_sessions,
    list_user_sessions,
    terminate_session,
    unsign_session_token,
)
from app.config import get_settings
from app.database import get_db
from app.models.bucket import Bucket, BucketType, BucketVisibility
from app.models.household import Household
from app.models.totp_recovery_code import TotpRecoveryCode
from app.models.user import User, UserRole
from app.models.webauthn_credential import WebauthnCredential
from app.schemas.auth import (
    ChangePasswordRequest,
    InviteRequest,
    LoginRequest,
    LoginTotpRequest,
    PasswordResetConfirm,
    PasswordResetRequest,
    RegisterRequest,
    RequiresTotpResponse,
    SessionInfo,
    UserResponse,
)
from app.services import totp
from app.services.audit import record_event
from app.services.crypto import decrypt_secret
from app.services.email import send_email
from app.services.email_templates import render_password_reset_email
from app.services.household_security import get_or_create_security_settings, lock_household_security

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()


async def _passkey_setup_required(db: AsyncSession, user: User) -> bool:
    """
    True nur für normale User (Konzept 4.1/4.3 — Passkey-Pflicht gilt nicht für Admins,
    dort ist der Passkey rein optionaler Passwort-Ersatz, TOTP bleibt Pflicht) ohne
    mindestens einen registrierten Passkey.
    """
    if user.role != UserRole.USER:
        return False

    result = await db.execute(
        select(func.count())
        .select_from(WebauthnCredential)
        .where(WebauthnCredential.user_id == user.id)
    )
    return result.scalar_one() == 0


async def _build_user_response(db: AsyncSession, user: User) -> UserResponse:
    """
    Baut UserResponse explizit statt über response_model=UserResponse automatisch aus dem
    User-ORM-Objekt (from_attributes) — passkey_setup_required ist kein direktes
    User-Attribut, sondern braucht einen eigenen Count-Query (_passkey_setup_required
    oben), den die automatische Konvertierung nicht leisten kann. Zentral hier statt an
    jeder UserResponse-Rückgabestelle dupliziert.
    """
    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        role=user.role,
        household_id=user.household_id,
        totp_enabled=user.totp_enabled,
        passkey_setup_required=await _passkey_setup_required(db, user),
    )


async def _finalize_first_factor(
    db: AsyncSession,
    user: User,
    response: Response,
    request: Request,
    *,
    success_event_type: str = "login_success",
) -> UserResponse | RequiresTotpResponse:
    """
    Gemeinsame Verzweigung NACH erfolgreichem ersten Faktor (Passwort ODER Passkey) —
    extrahiert aus login(), damit login() und der neue Passkey-Verify-Endpoint
    (app/api/webauthn.py) exakt dieselbe Admin/totp_enabled/Haushalt-Pflicht-Logik
    durchlaufen (DRY statt Duplikation). Ist TOTP für diesen User bereits eingerichtet
    oder haushaltsweit erzwungen, entsteht noch KEINE volle Session, sondern der
    Pre-Auth-Zustand aus app/auth/pending_2fa.py — die echte Session entsteht dann erst
    nach /auth/login/totp.

    `success_event_type` unterscheidet das Login-Audit-Event zwischen Passwort-
    ("login_success") und Passkey-Pfad ("passkey_login_success") — bei aktiver
    TOTP-Pflicht entsteht ohnehin kein Erfolgs-Event hier, das übernimmt erst
    /auth/login/totp nach dem zweiten Faktor.
    """
    security_settings = await get_or_create_security_settings(db, user.household_id)
    totp_required = user.totp_enabled or security_settings.totp_required_for_household

    if totp_required:
        await create_pending_2fa(user.id, response, request)
        await db.commit()  # persistiert eine ggf. lazy erstellte household_security_settings-Zeile
        return RequiresTotpResponse()

    user.last_login = datetime.now(UTC)
    await record_event(
        db,
        household_id=user.household_id,
        user_id=user.id,
        event_type=success_event_type,
        request=request,
    )

    await create_session(user.id, response, request)
    return await _build_user_response(db, user)


@router.get("/setup-required")
async def setup_required(db: AsyncSession = Depends(get_db)) -> dict[str, bool]:
    """
    Öffentlich (keine Auth nötig) — sagt dem Frontend, ob überhaupt schon ein User
    existiert. Frisch aufgesetzte Instanz zeigt den Einrichtungs-Assistenten statt
    eines Login-Formulars, für das es noch niemanden zum Anmelden gäbe.
    """
    result = await db.execute(select(User.id).limit(1))
    return {"setup_required": result.scalar_one_or_none() is None}


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterRequest, response: Response, request: Request, db: AsyncSession = Depends(get_db)
) -> UserResponse:
    """
    Legt einen neuen Haushalt mit dem ersten User (Rolle: Admin) an.
    Der Household-Bucket wird automatisch miterzeugt — is_default=True, immer 'transparent',
    darf laut Produkt-Konzept nie gelöscht oder auf privat gestellt werden.

    Früher wurde hier zusätzlich automatisch ein Demo-Beleg (is_demo=True) angelegt, damit
    man sofort etwas zum Testen hat. Das ist mit dem v1.0.0-Cutover entfernt worden (siehe
    Migration 0010) — offene Frage an den Nutzer, ob der First-Setup-Flow dadurch mit einer
    leeren Startseite ohne jeden Kontext startet und ob das UX-seitig ein Problem ist bzw.
    ersetzt werden soll (z.B. durch ein Onboarding-Leerzustand-Hinweis im Frontend).
    """
    existing = await db.execute(select(User).where(User.username == payload.username))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username bereits vergeben")

    household = Household(name=payload.household_name)
    db.add(household)
    await db.flush()  # household.id verfügbar machen, ohne bereits zu committen

    user = User(
        username=payload.username,
        email=payload.email,
        password_hash=hash_password(payload.password),
        role=UserRole.ADMIN,  # erster User eines Haushalts ist Admin
        household_id=household.id,
    )
    db.add(user)
    await db.flush()

    household_bucket = Bucket(
        household_id=household.id,
        owner_id=user.id,
        name="Haushalt",
        type=BucketType.HOUSEHOLD,
        visibility=BucketVisibility.TRANSPARENT,
        is_default=True,
    )
    db.add(household_bucket)
    await db.flush()

    await db.commit()
    await db.refresh(user)

    # Direkt einloggen, damit der Einrichtungs-Assistent im Frontend ohne separaten
    # Login-Schritt in die App übergeben kann.
    await create_session(user.id, response, request)
    return await _build_user_response(db, user)


@router.post(
    "/login",
    response_model=UserResponse | RequiresTotpResponse,
    dependencies=[Depends(rate_limit("login_ip", limit=20, window_seconds=900))],
)
async def login(
    payload: LoginRequest, response: Response, request: Request, db: AsyncSession = Depends(get_db)
) -> UserResponse | RequiresTotpResponse:
    """
    Zwei Rate-Limits gleichzeitig: das IP-only-Limit (20/15min, Schutz gegen Username-
    Enumeration-Sweeps über viele Accounts von einer IP) läuft als `Depends()` vor, weil es
    ausschließlich aus Request-Metadaten ableitbar ist. Das IP+Username-Limit (5/15min)
    braucht den Username aus dem Body — der ist erst verfügbar, nachdem FastAPI `payload`
    aufgelöst hat, also erst *innerhalb* der Funktion, nicht mehr über eine vorgeschaltete
    `Depends()`. Deshalb hier der direkte `check_rate_limit()`-Aufruf statt einer zweiten
    Dependency.

    Zweistufiger Login (Security-Hardening Phase 2): ist TOTP für diesen User bereits
    eingerichtet (totp_enabled) oder haushaltsweit erzwungen, wird noch KEINE volle Session
    angelegt — stattdessen ein Pre-Auth-Cookie (app/auth/pending_2fa.py) und
    `{"requires_totp": true}`. Die echte Session entsteht erst nach /auth/login/totp.

    Bewusst NICHT allein anhand der Admin-Rolle ausgelöst, obwohl TOTP für Admins laut
    Konzept verpflichtend ist: ein Admin ohne abgeschlossene Einrichtung (kein Secret, keine
    Recovery-Codes) könnte den zweiten Faktor sonst nie erfüllen — /auth/login/totp würde
    strukturell immer scheitern, mit keinem Weg zur Einrichtung (die eine echte Session
    voraussetzt). Das widerspräche dem Konzept-Prinzip "verhindert Aussperren durch
    Fehlkonfiguration" (Abschnitt 4.2). Die Admin-TOTP-Pflicht wird stattdessen als
    blockierendes Frontend-Gate nach dem Login durchgesetzt (kein App-Zugriff ohne
    abgeschlossene Einrichtung) — erst NACH erfolgreicher Einrichtung (totp_enabled=true)
    greift hier auch der Zwei-Faktor-Login-Zwang.
    """
    ip = get_client_ip(request)
    # Login akzeptiert Benutzername ODER E-Mail im selben Feld — beide sind laut
    # Registrierungs-/Einladungs-Flow bereits eindeutig (unique constraint), daher keine
    # Kollisionsgefahr zwischen den beiden Lookup-Varianten.
    result = await db.execute(
        select(User).where((User.username == payload.username) | (User.email == payload.username))
    )
    user = result.scalar_one_or_none()

    try:
        # Vor verify_password geprüft, um bei bereits gesperrten Kombinationen nicht
        # unnötig Argon2id-Rechenzeit zu verbrauchen.
        await check_rate_limit("login_ip_username", f"{ip}:{payload.username}", 5, 900)
    except HTTPException:
        # audit_log.household_id ist NOT NULL — nur loggen, wenn der Username zu einem
        # echten User (und damit Haushalt) gehört, sonst gäbe es keinen Haushalt-Bezug.
        if user is not None:
            await record_event(
                db,
                household_id=user.household_id,
                event_type="rate_limit_triggered",
                request=request,
                metadata={"endpoint": "/auth/login", "bucket": "login_ip_username"},
            )
        raise

    if user is not None:
        # Passkey-Exklusiv-Login (Security-Hardening Phase 4, Konzept 4.1): sperrt den
        # Passwort-Login haushaltsweit. Bewusst VOR verify_password geprüft (gleicher
        # Grund wie beim Rate-Limit oben — spart Argon2id-Rechenzeit für einen ohnehin
        # zum Scheitern verurteilten Login) und nur, wenn ein echter User aufgelöst wurde
        # (sonst gäbe es keinen Haushalt für den Settings-Lookup, analog zu den anderen
        # audit_log.household_id-NOT-NULL-Stellen in dieser Funktion).
        #
        # Bewusste Abweichung vom Enumeration-Schutz-Muster dieser Funktion: anders als
        # bei unbekanntem User/falschem Passwort (identische 401-Meldung) liefert dieser
        # Zweig einen eigenen 403 mit klartextlicher Begründung, wie vom Konzept
        # gefordert ("Passwort-Login ist für diesen Haushalt deaktiviert"). Das ist ein
        # bewusster Trade-off: für Haushalte mit aktivem Exklusiv-Schalter lässt sich
        # dadurch per Statuscode unterscheiden "Username existiert und Haushalt ist im
        # Exklusiv-Modus" von "falsches Passwort"/"unbekannter Username" (beide weiterhin
        # 401). Für das Zielsetting (2-Personen-Haushalt, nicht-öffentlich beworbene
        # Domain) wird das als akzeptabel bewertet — explizit im Bericht der Hauptinstanz
        # benannt, damit ein Security-Review das bei Bedarf gegenprüfen kann.
        security_settings = await get_or_create_security_settings(db, user.household_id)
        if security_settings.passkey_exclusive_login:
            await record_event(
                db,
                household_id=user.household_id,
                user_id=user.id,
                event_type="password_login_blocked",
                request=request,
                metadata={"reason": "passkey_exclusive_login"},
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Passwort-Login ist für diesen Haushalt deaktiviert — bitte mit Passkey anmelden.",
            )

    if user is None or not verify_password(payload.password, user.password_hash):
        # Bewusst identische Fehlermeldung für unbekannten User und falsches Passwort
        # (Enumeration-Schutz).
        #
        # Bewusste Abweichung vom Plan-Wortlaut: dort sollte JEDER fehlgeschlagene Login
        # (inkl. unbekanntem Username) als "login_failed" mit attempted_username auditiert
        # werden. audit_log.household_id ist aber NOT NULL, und bei unbekanntem Username
        # gibt es keinen User und damit keinen Haushalt, an den sich das Event hängen
        # ließe. household_id nachträglich auf nullable umzustellen hätte bedeutet, die
        # bereits gemergte/getestete Migration 0012 zu ändern — ausdrücklich nicht
        # gewünscht. Stattdessen: nur fehlgeschlagene Logins mit bekanntem User (falsches
        # Passwort) werden auditiert; unbekannte Usernamen erzeugen keinen audit_log-
        # Eintrag (sie bleiben aber weiterhin über die Rate-Limits oben gedeckelt).
        if user is not None:
            await record_event(
                db,
                household_id=user.household_id,
                event_type="login_failed",
                attempted_username=payload.username,
                request=request,
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Ungültige Anmeldedaten"
        )

    # Verzweigung (Admin/totp_enabled/Haushalt-Pflicht → Pre-Auth-TOTP-Zustand statt
    # direkter Session) ist in _finalize_first_factor() extrahiert — dieselbe Funktion
    # durchläuft auch der Passkey-Login (app/api/webauthn.py) nach erfolgreicher
    # Assertion-Verifikation.
    return await _finalize_first_factor(db, user, response, request)


@router.post(
    "/login/totp",
    response_model=UserResponse,
    dependencies=[Depends(rate_limit("login_totp_ip", limit=10, window_seconds=900))],
)
async def login_with_totp(
    payload: LoginTotpRequest,
    response: Response,
    request: Request,
    db: AsyncSession = Depends(get_db),
    pending_cookie: str | None = Cookie(default=None, alias=PENDING_2FA_COOKIE_NAME),
) -> UserResponse:
    """
    Zweiter Schritt des zweistufigen Logins (siehe login() oben). Der primäre Fehlversuchs-
    Zähler ist strikt an den Pending-Token selbst gebunden (app/auth/pending_2fa.py) — nach
    5 Fehlversuchen wird der Pre-Auth-State komplett verworfen; ein neuer Versuch muss
    wieder bei /auth/login beginnen (samt dessen eigenen IP-/Username-Rate-Limits).

    Zusätzlich (Security-Hardening-Nachbesserung) ein unabhängiges, zeitfensterbasiertes
    IP-Limit über `rate_limit()` (10 Versuche/15min) — nicht an den Pending-Token gebunden,
    sondern rein an die Client-IP. Deckt den Fall ab, dass der Pending-Token-Zähler selbst
    umgangen würde (z.B. wiederholt frische Pending-Tokens über /auth/login erzeugen und
    den 5er-Zähler so jedes Mal auf 0 zurücksetzen) — Brute-Force des 6-stelligen Codes
    bliebe dann trotzdem durch dieses Limit gedeckelt. Bewusst kein IP+Pending-Token-
    kombinierter Key: der Pending-Token wechselt ohnehin bei jedem /auth/login, ein
    kombinierter Key wäre pro Login-Versuch immer wieder bei 0 und liefe damit faktisch
    leer.

    `payload.code` nimmt sowohl den 6-stelligen TOTP-Code als auch einen Recovery-Code
    entgegen — die Unterscheidung erfolgt rein anhand des Formats (6 Ziffern vs. alles
    andere), kein separates Feld nötig.
    """
    user_id = await get_pending_user_id(pending_cookie)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Anmeldung abgelaufen oder ungültig — bitte erneut einloggen.",
        )

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        await destroy_pending_2fa(pending_cookie, response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Anmeldung abgelaufen oder ungültig — bitte erneut einloggen.",
        )

    normalized_code = payload.code.strip()
    verified = False
    event_type = "totp_login_success"
    used_recovery_code: TotpRecoveryCode | None = None

    if normalized_code.isdigit() and len(normalized_code) == 6 and user.totp_secret:
        try:
            secret = decrypt_secret(user.totp_secret)
            verified = totp.verify_code(secret, normalized_code)
        except ValueError:
            # ENCRYPTION_KEY wurde rotiert oder das Secret ist anderweitig nicht mehr
            # entschlüsselbar — wie ein falscher Code behandeln, nicht als 500 durchschlagen
            # lassen (analog zu _resolve_effective_provider_safe() in app/api/settings.py).
            verified = False
    else:
        recovery_codes = await db.execute(
            select(TotpRecoveryCode).where(
                TotpRecoveryCode.user_id == user.id, TotpRecoveryCode.used_at.is_(None)
            )
        )
        for recovery_code in recovery_codes.scalars().all():
            if totp.verify_recovery_code(payload.code, recovery_code.code_hash):
                used_recovery_code = recovery_code
                verified = True
                event_type = "recovery_code_used"
                break

    if not verified:
        # Bewusste Ergänzung über den Auftrags-Wortlaut hinaus (dort nur "Fehlversuch
        # zählen" gefordert): ein Audit-Event pro Fehlversuch, weil genau das laut
        # concepts/security-hardening.md Abschnitt 4.6 als sicherheitsrelevantes
        # "2FA-Event" gilt und household_id/user_id hier ohnehin schon geladen sind.
        discarded = await register_failed_attempt(pending_cookie)
        await record_event(
            db,
            household_id=user.household_id,
            user_id=user.id,
            event_type="totp_login_failed",
            request=request,
            metadata={"pending_state_discarded": discarded},
        )
        if discarded:
            await destroy_pending_2fa(pending_cookie, response)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Zu viele Fehlversuche — bitte erneut einloggen.",
            )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Ungültiger Code")

    if used_recovery_code is not None:
        # Echtes UPDATE, kein INSERT — totp_recovery_codes hat KEINEN Immutability-Trigger
        # wie audit_log (siehe Auftragskontext).
        used_recovery_code.used_at = datetime.now(UTC)

    await destroy_pending_2fa(pending_cookie, response)
    user.last_login = datetime.now(UTC)
    await record_event(
        db,
        household_id=user.household_id,
        user_id=user.id,
        event_type=event_type,
        request=request,
    )

    await create_session(user.id, response, request)
    return await _build_user_response(db, user)


@router.post("/password-reset/request", status_code=status.HTTP_204_NO_CONTENT)
async def request_password_reset(
    payload: PasswordResetRequest, request: Request, db: AsyncSession = Depends(get_db)
) -> None:
    """
    Immer 204, unabhängig davon ob die E-Mail einem User gehört (User-Enumeration-Schutz,
    analog zum Login-Kommentar oben). Mail-Versand ist bewusst in try/except gekapselt —
    ein Fehler darf niemals an den Client durchgereicht werden, sonst ließe sich über
    Erfolg/Fehler auf die Existenz der E-Mail schließen.

    Rate-Limits (IP+E-Mail und IP-only) brauchen die E-Mail aus dem Body, laufen deshalb
    hier direkt statt über `Depends()` (gleicher Grund wie beim IP+Username-Limit in
    `login()`).
    """
    ip = get_client_ip(request)
    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()

    for bucket, key, limit, window_seconds in (
        ("password_reset_ip", ip, 20, 3600),
        ("password_reset_ip_email", f"{ip}:{payload.email}", 3, 3600),
    ):
        try:
            await check_rate_limit(bucket, key, limit, window_seconds)
        except HTTPException:
            # Wie bei login_failed: nur loggen, wenn die E-Mail zu einem echten User (und
            # damit Haushalt) gehört — audit_log.household_id ist NOT NULL.
            if user is not None:
                await record_event(
                    db,
                    household_id=user.household_id,
                    event_type="rate_limit_triggered",
                    request=request,
                    metadata={"endpoint": "/auth/password-reset/request", "bucket": bucket},
                )
            raise

    if user is not None:
        token = await create_reset_token(user.id)
        link = f"{settings.public_app_url}/reset-password?token={token}"
        text_body = (
            "Hallo,\n\n"
            "für dein receiptly-Konto wurde ein Passwort-Reset angefordert. "
            f"Über folgenden Link kannst du ein neues Passwort vergeben:\n\n{link}\n\n"
            "Der Link ist gültig für 30 Minuten.\n\n"
            "Falls du das nicht angefordert hast, kannst du diese E-Mail ignorieren."
        )
        try:
            await send_email(
                db,
                to=user.email,
                subject="receiptly – Passwort zurücksetzen",
                text_body=text_body,
                html_body=render_password_reset_email(link),
            )
        except Exception:
            logger.exception("Versand der Passwort-Reset-Mail an %s fehlgeschlagen", user.email)


@router.post("/password-reset/confirm", status_code=status.HTTP_204_NO_CONTENT)
async def confirm_password_reset(
    payload: PasswordResetConfirm, request: Request, db: AsyncSession = Depends(get_db)
) -> None:
    user_id = await consume_reset_token(payload.token)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Link ungültig oder abgelaufen — bitte neu anfordern.",
        )

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Link ungültig oder abgelaufen — bitte neu anfordern.",
        )

    user.password_hash = hash_password(payload.new_password)
    # Teilt sich den Commit mit record_event(commit=True) — kein separates db.commit() nötig.
    await record_event(
        db,
        household_id=user.household_id,
        user_id=user.id,
        event_type="password_reset_confirmed",
        request=request,
    )

    # Keine aktive Session im Reset-Confirm-Flow (Link kam per Mail, kein eingeloggter
    # Browser) — deshalb alle bestehenden Sessions des Users invalidieren, nicht nur andere.
    await invalidate_other_sessions(user.id, keep_raw_token=None)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    session_cookie: str | None = Cookie(default=None, alias=settings.session_cookie_name),
) -> None:
    """
    Bewusst ohne `Depends(get_current_user)` — Logout muss auch bei bereits abgelaufener
    oder ungültiger Session klaglos das Cookie löschen (idempotent). Der Audit-Eintrag wird
    deshalb nur geschrieben, wenn die Session zum Aufrufzeitpunkt noch auflösbar war.
    """
    raw_token = await unsign_session_token(session_cookie, enforce_max_age=False)
    if raw_token:
        user_id = await get_user_id_by_raw_token(raw_token)
        if user_id is not None:
            result = await db.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()
            if user is not None:
                await record_event(
                    db,
                    household_id=user.household_id,
                    user_id=user.id,
                    event_type="logout",
                    request=request,
                )

    await destroy_session(session_cookie, response)


@router.get("/me", response_model=UserResponse)
async def me(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> UserResponse:
    return await _build_user_response(db, user)


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    payload: ChangePasswordRequest,
    request: Request,
    user: User = Depends(require_totp_enrolled),
    raw_token: str | None = Depends(get_current_raw_session_token),
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Verlangt das aktuelle Passwort erneut (Argon2id) — eine gekaperte Session allein darf
    nicht reichen, um das Passwort zu ändern. Bei Erfolg werden alle anderen Sessions des
    Users invalidiert, die aktuelle (die die Änderung ausgelöst hat) bleibt bestehen.

    Rate-Limit ist an `user_id` gebunden, nicht IP: der User ist hier schon über
    `get_current_user` authentifiziert, und mehrere Haushaltsmitglieder können sich eine
    IP teilen — IP wäre hier ein schwächerer und potenziell falscher Schutzfaktor. Läuft
    deshalb per direktem `check_rate_limit()`-Aufruf statt `Depends()`, weil `user.id`
    erst nach Auflösung der `get_current_user`-Dependency verfügbar ist.
    """
    try:
        await check_rate_limit("change_password", str(user.id), 5, 3600)
    except HTTPException:
        # User ist hier immer bekannt (Dependency), household_id also immer verfügbar —
        # anders als bei den Pre-Auth-Limits oben kann hier immer auditiert werden.
        await record_event(
            db,
            household_id=user.household_id,
            user_id=user.id,
            event_type="rate_limit_triggered",
            request=request,
            metadata={"endpoint": "/auth/change-password", "bucket": "change_password"},
        )
        raise

    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Aktuelles Passwort ist falsch"
        )

    user.password_hash = hash_password(payload.new_password)
    # Teilt sich den Commit mit record_event(commit=True) — kein separates db.commit() nötig.
    await record_event(
        db,
        household_id=user.household_id,
        user_id=user.id,
        event_type="password_changed",
        request=request,
    )

    await invalidate_other_sessions(user.id, keep_raw_token=raw_token)


@router.get("/sessions", response_model=list[SessionInfo])
async def get_sessions(
    user: User = Depends(require_totp_enrolled),
    raw_token: str | None = Depends(get_current_raw_session_token),
) -> list[dict]:
    """Eigene aktive Sessions (Device/Browser, IP, last_seen_at) — nie der rohe Token, nur session_id."""
    return await list_user_sessions(user.id, raw_token)


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(
    session_id: uuid.UUID,
    request: Request,
    user: User = Depends(require_totp_enrolled),
    raw_token: str | None = Depends(get_current_raw_session_token),
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Beendet eine fremde Session des eigenen Accounts. Die aktuelle Session lässt sich
    hierüber nicht beenden (dafür ist /auth/logout da) — terminate_session() lehnt das
    serverseitig ab, hier wird das vorab geprüft, um 400 (aktuelle Session) von 404
    (nicht gefunden) unterscheiden zu können.
    """
    sessions = await list_user_sessions(user.id, raw_token)
    matching = next((s for s in sessions if s["session_id"] == session_id), None)
    if matching is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session nicht gefunden")
    if matching["is_current"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Die aktuelle Session kann nicht hierüber beendet werden — nutze Logout.",
        )

    terminated = await terminate_session(user.id, session_id, raw_token)
    if not terminated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session nicht gefunden")

    await record_event(
        db,
        household_id=user.household_id,
        user_id=user.id,
        event_type="session_terminated",
        request=request,
        metadata={"terminated_session_id": str(session_id)},
    )


@router.get("/household-members", response_model=list[UserResponse])
async def list_household_members(
    user: User = Depends(require_totp_enrolled), db: AsyncSession = Depends(get_db)
) -> list[UserResponse]:
    """Alle User im selben Haushalt — Grundlage für die Bucket-Freigabe-Auswahl."""
    result = await db.execute(select(User).where(User.household_id == user.household_id))
    members = list(result.scalars().all())
    # Ein Count-Query pro Mitglied (_build_user_response) statt eines Batch-Querys — für
    # die Zielgruppe (Konzept: 2-Personen-Haushalt) ist das N+1 hier vernachlässigbar,
    # ein Batch-Join wäre unnötige Komplexität für diese Größenordnung.
    return [await _build_user_response(db, member) for member in members]


@router.post("/invite", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def invite_household_member(
    payload: InviteRequest,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """
    Legt einen weiteren User im selben Haushalt an (kein neuer Household wie bei /register).
    Admin-only, da damit potenziell Zugriff auf den transparenten Household-Bucket entsteht.

    Bewusste Ergänzung über den ursprünglichen Phase-4-Auftrag hinaus (Precondition-Gate/
    Login-Ablehnung/Löschschutz): ist der Passkey-Exklusiv-Login bereits aktiv, wird die
    Einladung selbst mit 409 abgelehnt. Grund: das neue Mitglied hätte weder Passwort-
    Login (durch den Exklusiv-Schalter gesperrt) noch einen Passkey (kann erst NACH einer
    ersten Session unter /webauthn/register/* registriert werden) — ein struktureller
    Lockout für genau dieses eine neue Mitglied, den das Konzept mit dem
    Precondition-Gate eigentlich ausschließen wollte ("Da neue User ohnehin beim ersten
    Login zur Passkey-Einrichtung gezwungen werden, bleibt die Invariante 'alle User haben
    einen Passkey' automatisch erhalten"). Diese Annahme stimmt nur, solange Einladungen
    bei aktivem Schalter verhindert werden — sonst würde ein danach eingeladenes Mitglied
    die Invariante durchbrechen, ohne dass die Aktivierung selbst das je hätte verhindern
    können. Rettungsweg: Admin deaktiviert den Exklusiv-Schalter temporär, lädt ein,
    lässt das neue Mitglied per Passwort einloggen + einen Passkey einrichten, aktiviert
    danach wieder (Precondition-Gate greift dann erneut ganz normal).

    lock_household_security() muss vor dem Gate-Check unten stehen (Security-Review
    Phase 4, M2): sonst kann dieser Guard den Schalter noch als "aus" lesen, während
    parallel ein Aktivierungs-PUT (app/api/security_settings.py) kurz vor dem Commit
    steht — das neue Mitglied würde dann ohne Passkey angelegt, kurz bevor der Exklusiv-
    Modus scharf geschaltet wird.
    """
    await lock_household_security(db, admin.household_id)
    existing = await db.execute(select(User).where(User.username == payload.username))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username bereits vergeben")

    security_settings = await get_or_create_security_settings(db, admin.household_id)
    if security_settings.passkey_exclusive_login:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Neue Mitglieder können nicht eingeladen werden, solange der Passkey-"
                "Exklusiv-Login aktiv ist — das neue Mitglied hätte sonst weder Passwort- "
                "noch Passkey-Login. Bitte den Exklusiv-Modus vorübergehend deaktivieren, "
                "einladen und dort einen Passkey einrichten lassen, danach kann der "
                "Exklusiv-Modus wieder aktiviert werden."
            ),
        )

    member = User(
        username=payload.username,
        email=payload.email,
        password_hash=hash_password(payload.password),
        role=UserRole.USER,
        household_id=admin.household_id,
    )
    db.add(member)
    await db.commit()
    await db.refresh(member)
    return await _build_user_response(db, member)
