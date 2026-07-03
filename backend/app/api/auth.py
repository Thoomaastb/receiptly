from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.auth.security import hash_password, verify_password
from app.auth.session import create_session, destroy_session
from app.config import get_settings
from app.database import get_db
from app.models.bucket import Bucket, BucketType, BucketVisibility
from app.models.household import Household
from app.models.user import User, UserRole
from app.schemas.auth import LoginRequest, RegisterRequest, UserResponse

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, db: AsyncSession = Depends(get_db)) -> User:
    """
    Legt einen neuen Haushalt mit dem ersten User (Rolle: Admin) an.
    Der Household-Bucket wird automatisch miterzeugt — is_default=True, immer 'transparent',
    darf laut Produkt-Konzept nie gelöscht oder auf privat gestellt werden.
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

    await db.commit()
    await db.refresh(user)
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


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    session_cookie: str | None = Cookie(default=None, alias=settings.session_cookie_name),
) -> None:
    await destroy_session(session_cookie, response)


@router.get("/me", response_model=UserResponse)
async def me(user: User = Depends(get_current_user)) -> User:
    return user
