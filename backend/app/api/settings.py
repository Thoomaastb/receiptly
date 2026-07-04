from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_admin
from app.database import get_db
from app.models.ai_settings import AISettings, AIProviderType
from app.models.user import User
from app.schemas.ai_settings import AISettingsResponse, AISettingsUpdate
from app.services.crypto import encrypt_secret

router = APIRouter(prefix="/settings", tags=["settings"])


async def _get_or_create(db: AsyncSession, household_id) -> AISettings:
    result = await db.execute(select(AISettings).where(AISettings.household_id == household_id))
    settings = result.scalar_one_or_none()
    if settings is None:
        settings = AISettings(household_id=household_id, provider=AIProviderType.OLLAMA)
        db.add(settings)
        await db.flush()
    return settings


@router.get("/ai-provider", response_model=AISettingsResponse)
async def get_ai_provider(
    admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)
) -> AISettingsResponse:
    settings = await _get_or_create(db, admin.household_id)
    await db.commit()
    return AISettingsResponse(
        provider=settings.provider.value,
        has_api_key=settings.encrypted_api_key is not None,
        custom_endpoint=settings.custom_endpoint,
    )


@router.put("/ai-provider", response_model=AISettingsResponse)
async def update_ai_provider(
    payload: AISettingsUpdate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> AISettingsResponse:
    """
    Admin-only. Der Key wird nie im Klartext gespeichert oder zurückgegeben —
    nur has_api_key als Boolean. Leeres api_key-Feld lässt einen vorhandenen
    Key unverändert (z.B. wenn nur der Provider gewechselt wird).
    """
    settings = await _get_or_create(db, admin.household_id)

    settings.provider = AIProviderType(payload.provider)
    if payload.provider == AIProviderType.OLLAMA.value:
        # Lokal, kein Key nötig — alten externen Key nicht stillschweigend weiterverwenden
        settings.encrypted_api_key = None
        settings.custom_endpoint = None
    else:
        if payload.api_key:
            settings.encrypted_api_key = encrypt_secret(payload.api_key)
        if payload.custom_endpoint is not None:
            settings.custom_endpoint = payload.custom_endpoint

    await db.commit()
    await db.refresh(settings)

    return AISettingsResponse(
        provider=settings.provider.value,
        has_api_key=settings.encrypted_api_key is not None,
        custom_endpoint=settings.custom_endpoint,
    )
