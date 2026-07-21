from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user, require_totp_enrolled
from app.database import get_db
from app.models.audit_log import AuditLog
from app.models.user import User, UserRole
from app.schemas.audit import AuditLogEntry

router = APIRouter(
    prefix="/audit-log",
    tags=["audit-log"],
    # Siehe app/api/receipts.py — dasselbe Router-weite TOTP-Enrollment-Gate.
    dependencies=[Depends(require_totp_enrolled)],
)


@router.get("", response_model=list[AuditLogEntry])
async def list_audit_log(
    scope: Literal["own", "household"] = "own",
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[AuditLogEntry]:
    """
    `scope="own"` (Default) zeigt nur Events des eigenen Accounts — für jeden User.
    `scope="household"` zeigt alle Events des Haushalts, unabhängig vom auslösenden User
    — Admin-only (403 sonst), wie laut Security-Hardening-Plan für Phase 2 vorgesehen.
    Bewusst ein manueller Rollen-Check statt `Depends(require_admin)`: `require_admin`
    würde für JEDEN Aufruf (auch `scope="own"`) eine 403 für Nicht-Admins erzwingen, hier
    soll aber nur `scope="household"` Admin-only sein — das lässt sich mit `Depends()`
    nicht bedingt an einen Query-Parameter koppeln.

    In beiden Fällen wird zusätzlich der Username des auslösenden Users mitgeliefert
    (LEFT JOIN, da `audit_log.user_id` bei Events ohne bekannten User bzw. nach
    Account-Löschung NULL sein kann — siehe app/models/audit_log.py) — bei
    `scope="household"` ist das die einzige Möglichkeit, Events verschiedener
    Haushaltsmitglieder in der UI zu unterscheiden.

    Neueste zuerst. Anders als bei list_receipts() (dort ist `limit` optional, Default =
    alle) hier ein festes Default-Limit von 50: audit_log wächst unbegrenzt mit jedem
    sicherheitsrelevanten Ereignis, ein "alles laden"-Default wäre hier auf Dauer riskanter
    als bei den durch Haushaltsaktivität natürlich begrenzten Belegen.
    """
    if scope == "household" and user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Admin-Rechte erforderlich"
        )

    scope_filter = (
        AuditLog.household_id == user.household_id
        if scope == "household"
        else AuditLog.user_id == user.id
    )

    stmt = (
        select(AuditLog, User.username)
        .outerjoin(User, User.id == AuditLog.user_id)
        .where(scope_filter)
        .order_by(AuditLog.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    result = await db.execute(stmt)

    return [
        AuditLogEntry(
            id=entry.id,
            event_type=entry.event_type,
            ip=entry.ip,
            user_agent=entry.user_agent,
            attempted_username=entry.attempted_username,
            event_metadata=entry.event_metadata,
            created_at=entry.created_at,
            user_id=entry.user_id,
            username=username,
        )
        for entry, username in result.all()
    ]
