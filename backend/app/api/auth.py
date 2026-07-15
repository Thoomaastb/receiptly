import logging
from datetime import date, timedelta

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user, require_admin
from app.auth.password_reset import consume_reset_token, create_reset_token
from app.auth.security import hash_password, verify_password
from app.auth.session import create_session, destroy_session
from app.config import get_settings
from app.database import get_db
from app.models.bucket import Bucket, BucketType, BucketVisibility
from app.models.household import Household
from app.models.receipt import Receipt, ReceiptStatus
from app.models.user import User, UserRole
from app.schemas.auth import (
    InviteRequest,
    LoginRequest,
    PasswordResetConfirm,
    PasswordResetRequest,
    RegisterRequest,
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
    payload: RegisterRequest, response: Response, db: AsyncSession = Depends(get_db)
) -> User:
    """
    Legt einen neuen Haushalt mit dem ersten User (Rolle: Admin) an.
    Der Household-Bucket wird automatisch miterzeugt — is_default=True, immer 'transparent',
    darf laut Produkt-Konzept nie gelöscht oder auf privat gestellt werden.
    Ein Demo-Beleg (is_demo=True) landet ebenfalls automatisch drin, damit man sofort
    etwas zum Testen hat — wird beim v1.0.0-Cutover per eigener Migration entfernt.
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

    demo_receipt = Receipt(
        user_id=user.id,
        bucket_id=household_bucket.id,
        file_path="demo/dummy-beleg.jpg",
        content_hash=f"demo-{household_bucket.id}",
        status=ReceiptStatus.PROCESSED,
        currency="EUR",
        receipt_date=date.today() - timedelta(days=3),
        total_amount=24.99,
        is_demo=True,
    )
    db.add(demo_receipt)

    await db.commit()
    await db.refresh(user)

    # Direkt einloggen, damit der Einrichtungs-Assistent im Frontend ohne separaten
    # Login-Schritt in die App übergeben kann.
    await create_session(user.id, response)
    return user


@router.post("/login", response_model=UserResponse)
async def login(
    payload: LoginRequest, response: Response, db: AsyncSession = Depends(get_db)
) -> User:
    result = await db.execute(select(User).where(User.username == payload.username))
    user = result.scalar_one_or_none()

    if user is None or not verify_password(payload.password, user.password_hash):
        # Bewusst identische Fehlermeldung für unbekannten User und falsches Passwort
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Ungültige Anmeldedaten"
        )

    await create_session(user.id, response)
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
    # Bewusst NICHT im Scope: bestehende Sessions des Users invalidieren — bräuchte einen
    # Rückwärts-Index user_id→Sessions in session.py, geplant für v0.23.0 "Sitzungsverwaltung".
    await db.commit()


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    session_cookie: str | None = Cookie(default=None, alias=settings.session_cookie_name),
) -> None:
    await destroy_session(session_cookie, response)


@router.get("/me", response_model=UserResponse)
async def me(user: User = Depends(get_current_user)) -> User:
    return user


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
