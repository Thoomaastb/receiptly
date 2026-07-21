"""GET/PUT haushaltsweite Sicherheitsrichtlinien — beide Endpoints Admin-only."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_admin
from app.database import get_db
from app.models.user import User
from app.schemas.security_settings import SecurityPolicyResponse, SecurityPolicyUpdate
from app.services.household_security import get_or_create_security_settings

router = APIRouter(prefix="/settings", tags=["security-settings"])


@router.get("/security-policy", response_model=SecurityPolicyResponse)
async def get_security_policy(
    admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)
) -> SecurityPolicyResponse:
    settings = await get_or_create_security_settings(db, admin.household_id)
    await db.commit()
    return SecurityPolicyResponse.model_validate(settings)


@router.put("/security-policy", response_model=SecurityPolicyResponse)
async def update_security_policy(
    payload: SecurityPolicyUpdate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> SecurityPolicyResponse:
    settings = await get_or_create_security_settings(db, admin.household_id)

    settings.totp_required_for_household = payload.totp_required_for_household
    settings.audit_retention_days = payload.audit_retention_days
    settings.log_attempted_username = payload.log_attempted_username

    await db.commit()
    await db.refresh(settings)
    return SecurityPolicyResponse.model_validate(settings)
