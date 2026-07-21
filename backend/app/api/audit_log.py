from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models.audit_log import AuditLog
from app.models.user import User
from app.schemas.audit import AuditLogEntry

router = APIRouter(prefix="/audit-log", tags=["audit-log"])


@router.get("", response_model=list[AuditLogEntry])
async def list_audit_log(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[AuditLog]:
    """
    Nur Eigensicht (`user_id == current_user.id`) — die haushaltsweite Admin-Sicht kommt
    laut Security-Hardening-Plan erst in Phase 2 zusammen mit den Haushalt-Sicherheits-
    richtlinien. Neueste zuerst.

    Anders als bei list_receipts() (dort ist `limit` optional, Default = alle) hier ein
    festes Default-Limit von 50: audit_log wächst unbegrenzt mit jedem sicherheitsrelevanten
    Ereignis, ein "alles laden"-Default wäre hier auf Dauer riskanter als bei den durch
    Haushaltsaktivität natürlich begrenzten Belegen.
    """
    stmt = (
        select(AuditLog)
        .where(AuditLog.user_id == user.id)
        .order_by(AuditLog.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())
