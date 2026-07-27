"""GET/PUT instanzweiter Schalter für den automatischen Update-Check — Singleton-Muster
analog zu app/api/smtp_settings.py, aber ohne Server-Lock/.env-Override (siehe
app/models/update_check_settings.py). Alle Endpoints Admin-only.
"""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_admin
from app.database import get_db
from app.models.update_check_settings import UpdateCheckSettings
from app.models.user import User
from app.schemas.update_check_settings import (
    UpdateCheckSettingsResponse,
    UpdateCheckSettingsUpdate,
)

router = APIRouter(prefix="/settings/update-check", tags=["update-check-settings"])


async def _get_or_create(db: AsyncSession) -> UpdateCheckSettings:
    result = await db.execute(select(UpdateCheckSettings).where(UpdateCheckSettings.id == 1))
    settings = result.scalar_one_or_none()
    if settings is None:
        settings = UpdateCheckSettings(id=1, enabled=True)
        db.add(settings)
        await db.flush()
    return settings


@router.get("", response_model=UpdateCheckSettingsResponse)
async def get_update_check_settings(
    admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)
) -> UpdateCheckSettings:
    settings = await _get_or_create(db)
    await db.commit()
    return settings


@router.put("", response_model=UpdateCheckSettingsResponse)
async def update_update_check_settings(
    payload: UpdateCheckSettingsUpdate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> UpdateCheckSettings:
    settings = await _get_or_create(db)
    settings.enabled = payload.enabled

    await db.commit()
    await db.refresh(settings)

    return settings
