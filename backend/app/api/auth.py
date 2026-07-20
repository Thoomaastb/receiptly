import logging
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_raw_session_token, get_current_user, require_admin
from app.auth.password_reset import consume_reset_token, create_reset_token
from app.auth.security import hash_password, verify_password
from app.auth.session import (
    create_session,
    destroy_session,
    invalidate_other_sessions,
    list_user_sessions,
    terminate_session,
)
from app.config import get_settings
from app.database import get_db
from app.models.bucket import Bucket, BucketType, BucketVisibility
from app.models.household import Household
from app.models.user import User, UserRole
from app.schemas.auth import (
    ChangePasswordRequest,
    InviteRequest,
    LoginRequest,
    PasswordResetConfirm,
    PasswordResetRequest,
    RegisterRequest,
    SessionInfo,
    UserResponse,
)
from app.services.email import send_email

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()


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
) -> User:
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
    return user


@router.post("/login", response_model=UserResponse)
async def login(
    payload: LoginRequest, response: Response, request: Request, db: AsyncSession = Depends(get_db)
) -> User:
    result = await db.execute(select(User).where(User.username == payload.username))
    user = result.scalar_one_or_none()

    if user is None or not verify_password(payload.password, user.password_hash):
        # Bewusst identische Fehlermeldung für unbekannten User und falsches Passwort
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Ungültige Anmeldedaten"
        )

    # Nur nach erfolgreicher Passwortprüfung schreiben — ein Write bei fehlgeschlagenem
    # Login wäre ein Timing-/Enumeration-Seitenkanal (siehe Kommentar oben).
    user.last_login = datetime.now(UTC)
    await db.commit()

    await create_session(user.id, response, request)
    return user


@router.post("/password-reset/request", status_code=status.HTTP_204_NO_CONTENT)
async def request_password_reset(
    payload: PasswordResetRequest, db: AsyncSession = Depends(get_db)
) -> None:
    """
    Immer 204, unabhängig davon ob die E-Mail einem User gehört (User-Enumeration-Schutz,
    analog zum Login-Kommentar oben). Mail-Versand ist bewusst in try/except gekapselt —
    ein Fehler darf niemals an den Client durchgereicht werden, sonst ließe sich über
    Erfolg/Fehler auf die Existenz der E-Mail schließen.
    """
    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()

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
                to=user.email, subject="receiptly – Passwort zurücksetzen", text_body=text_body
            )
        except Exception:
            logger.exception("Versand der Passwort-Reset-Mail an %s fehlgeschlagen", user.email)


@router.post("/password-reset/confirm", status_code=status.HTTP_204_NO_CONTENT)
async def confirm_password_reset(
    payload: PasswordResetConfirm, db: AsyncSession = Depends(get_db)
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
    await db.commit()

    # Keine aktive Session im Reset-Confirm-Flow (Link kam per Mail, kein eingeloggter
    # Browser) — deshalb alle bestehenden Sessions des Users invalidieren, nicht nur andere.
    await invalidate_other_sessions(user.id, keep_raw_token=None)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    session_cookie: str | None = Cookie(default=None, alias=settings.session_cookie_name),
) -> None:
    await destroy_session(session_cookie, response)


@router.get("/me", response_model=UserResponse)
async def me(user: User = Depends(get_current_user)) -> User:
    return user


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    payload: ChangePasswordRequest,
    user: User = Depends(get_current_user),
    raw_token: str | None = Depends(get_current_raw_session_token),
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Verlangt das aktuelle Passwort erneut (Argon2id) — eine gekaperte Session allein darf
    nicht reichen, um das Passwort zu ändern. Bei Erfolg werden alle anderen Sessions des
    Users invalidiert, die aktuelle (die die Änderung ausgelöst hat) bleibt bestehen.
    """
    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Aktuelles Passwort ist falsch"
        )

    user.password_hash = hash_password(payload.new_password)
    await db.commit()

    await invalidate_other_sessions(user.id, keep_raw_token=raw_token)


@router.get("/sessions", response_model=list[SessionInfo])
async def get_sessions(
    user: User = Depends(get_current_user),
    raw_token: str | None = Depends(get_current_raw_session_token),
) -> list[dict]:
    """Eigene aktive Sessions (Device/Browser, IP, last_seen_at) — nie der rohe Token, nur session_id."""
    return await list_user_sessions(user.id, raw_token)


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(
    session_id: uuid.UUID,
    user: User = Depends(get_current_user),
    raw_token: str | None = Depends(get_current_raw_session_token),
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


@router.get("/household-members", response_model=list[UserResponse])
async def list_household_members(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> list[User]:
    """Alle User im selben Haushalt — Grundlage für die Bucket-Freigabe-Auswahl."""
    result = await db.execute(select(User).where(User.household_id == user.household_id))
    return list(result.scalars().all())


@router.post("/invite", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def invite_household_member(
    payload: InviteRequest,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Legt einen weiteren User im selben Haushalt an (kein neuer Household wie bei /register).
    Admin-only, da damit potenziell Zugriff auf den transparenten Household-Bucket entsteht.
    """
    existing = await db.execute(select(User).where(User.username == payload.username))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username bereits vergeben")

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
    return member
