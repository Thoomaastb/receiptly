from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.session import get_session_user_id
from app.config import get_settings
from app.database import get_db
from app.models.user import User, UserRole

settings = get_settings()


async def get_current_user(
    db: AsyncSession = Depends(get_db),
    session_cookie: str | None = Cookie(default=None, alias=settings.session_cookie_name),
) -> User:
    """
    Liest die Session-Cookie (Name aus Settings, siehe session_cookie_name) und lädt den User.
    Wirft 401, wenn keine gültige Session vorliegt.
    """
    user_id = await get_session_user_id(session_cookie)
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Nicht angemeldet")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Nicht angemeldet")
    return user


async def require_admin(user: User = Depends(get_current_user)) -> User:
    """RBAC-Gate: nur Admins. Unabhängig von Bucket-Sichtbarkeit (zwei getrennte Achsen)."""
    if user.role != UserRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin-Rechte erforderlich")
    return user
