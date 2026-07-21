import logging

from fastapi import Cookie, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.request_meta import get_client_ip, get_user_agent
from app.auth.session import get_user_id_by_raw_token, touch_session, unsign_session_token
from app.config import get_settings
from app.database import get_db
from app.models.user import User, UserRole

logger = logging.getLogger(__name__)
settings = get_settings()


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
    session_cookie: str | None = Cookie(default=None, alias=settings.session_cookie_name),
) -> User:
    """
    Liest die Session-Cookie (Name aus Settings, siehe session_cookie_name) und lädt den User.
    Wirft 401, wenn keine gültige Session vorliegt.
    """
    raw_token = await unsign_session_token(session_cookie)
    user_id = await get_user_id_by_raw_token(raw_token) if raw_token else None
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Nicht angemeldet")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Nicht angemeldet")

    if raw_token:
        try:
            await touch_session(raw_token, get_client_ip(request), get_user_agent(request))
        except Exception:
            # Ein Redis-Hiccup beim Metadaten-Update darf eine ansonsten gültige
            # Authentifizierung niemals scheitern lassen.
            logger.exception("touch_session fehlgeschlagen, Auth bleibt trotzdem gültig")

    return user


async def get_current_raw_session_token(
    session_cookie: str | None = Cookie(default=None, alias=settings.session_cookie_name),
) -> str | None:
    """Rohen Session-Token aus dem signierten Cookie lösen — für Endpoints, die ihn direkt brauchen."""
    return await unsign_session_token(session_cookie)


async def require_totp_enrolled(user: User = Depends(get_current_user)) -> User:
    """
    Zusätzliches Gate NACH get_current_user: erzwingt serverseitig, dass ein Admin mit
    `totp_enabled=false` außer den Grundfunktionen (/auth/me, /auth/logout) und der
    TOTP-Einrichtung selbst (app/api/totp.py) NICHTS nutzen kann. login() in app/api/auth.py
    erzwingt den zweiten Faktor bewusst NICHT allein anhand der Admin-Rolle (siehe Kommentar
    dort — würde einen Admin ohne abgeschlossene Einrichtung strukturell aussperren), das
    Frontend-Gate in +layout.svelte blockiert bislang nur die SPA-UI, nicht direkte API-
    Calls. Diese Dependency schließt genau diese Lücke serverseitig.

    Bewusst NICHT auf app/api/totp.py angewendet — dort muss ein Admin ohne totp_enabled
    weiterhin /enroll und /confirm erreichen können, sonst gäbe es keinen Weg zur
    Einrichtung mehr (derselbe Lockout, den login() vermeidet). Ebenso nicht auf /auth/me
    und /auth/logout (app/api/auth.py) — die müssen für jeden authentifizierten User immer
    erreichbar bleiben.
    """
    if user.role == UserRole.ADMIN and not user.totp_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="TOTP-Einrichtung muss zuerst abgeschlossen werden.",
        )
    return user


async def require_admin(user: User = Depends(require_totp_enrolled)) -> User:
    """
    RBAC-Gate: nur Admins. Unabhängig von Bucket-Sichtbarkeit (zwei getrennte Achsen).
    Hängt bewusst an require_totp_enrolled statt direkt an get_current_user: jeder
    Admin-only-Endpoint (require_admin) soll automatisch auch das TOTP-Enrollment-Gate
    mitbekommen, ohne es an jeder Stelle separat verdrahten zu müssen. Für Nicht-Admins
    ändert sich nichts — require_totp_enrolled greift nur bei role == ADMIN.
    """
    if user.role != UserRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin-Rechte erforderlich")
    return user
