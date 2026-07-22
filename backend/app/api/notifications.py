import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user, require_totp_enrolled
from app.database import get_db
from app.models.user import User
from app.schemas.notification import NotificationResponse, UnreadCountResponse
from app.services.notifications import count_unread, list_notifications, mark_all_read, mark_read

router = APIRouter(
    prefix="/notifications",
    tags=["notifications"],
    # Router-weites Gate wie receipts.py — Notifications ist ein Post-Enrollment-Feature,
    # kein Bootstrap-Endpoint wie auth.py/totp.py/webauthn.py.
    dependencies=[Depends(require_totp_enrolled)],
)


@router.get("", response_model=list[NotificationResponse])
async def get_notifications(
    category: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[NotificationResponse]:
    return await list_notifications(
        db, user_id=user.id, category=category, limit=limit, offset=offset
    )


@router.get("/unread-count", response_model=UnreadCountResponse)
async def get_unread_count(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UnreadCountResponse:
    counts = await count_unread(db, user_id=user.id)
    return UnreadCountResponse(**counts)


@router.post("/{notification_id}/read", status_code=status.HTTP_204_NO_CONTENT)
async def read_notification(
    notification_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    marked = await mark_read(db, user_id=user.id, notification_id=notification_id)
    if not marked:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Notification nicht gefunden"
        )


@router.post("/read-all", status_code=status.HTTP_204_NO_CONTENT)
async def read_all_notifications(
    category: str | None = Query(default=None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    await mark_all_read(db, user_id=user.id, category=category)
