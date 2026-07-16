import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.ai_settings import AISettings, AIProviderType
from app.services.crypto import decrypt_secret

settings = get_settings()


@dataclass
class EffectiveProviderConfig:
    provider: AIProviderType
    endpoint: str | None  # nur für Ollama relevant (Server- oder Haushalts-Host)
    model_name: str | None
    api_key: str | None  # Klartext, ggf. bereits entschlüsselt; None bei Ollama
    locked_by_server: bool


async def _load_ai_settings(db: AsyncSession, household_id: uuid.UUID) -> AISettings | None:
    result = await db.execute(select(AISettings).where(AISettings.household_id == household_id))
    return result.scalar_one_or_none()


async def resolve_effective_provider(
    db: AsyncSession, household_id: uuid.UUID
) -> EffectiveProviderConfig | None:
    """
    3-stufige Prioritätskette (siehe .env.example): server-weiter OLLAMA_HOST-Fallback >
    server-weiter AI_HOST-Fallback > haushaltsweite AISettings-Zeile > None (nur lokale
    Texterfassung, keine KI-Strukturierung). Genutzt von app/services/ai_extraction.py und
    app/api/settings.py (für locked_by_server/effective_* in der GET-Response).
    """
    if settings.ollama_host:
        return EffectiveProviderConfig(
            provider=AIProviderType.OLLAMA,
            endpoint=settings.ollama_host,
            model_name=settings.ollama_model,
            api_key=None,
            locked_by_server=True,
        )
    if settings.ai_host:
        return EffectiveProviderConfig(
            provider=AIProviderType(settings.ai_host),
            endpoint=None,
            model_name=None,
            api_key=settings.ai_key,
            locked_by_server=True,
        )

    ai_settings = await _load_ai_settings(db, household_id)
    if ai_settings is not None and ai_settings.provider is not None:
        if ai_settings.provider == AIProviderType.OLLAMA:
            # Haushaltseigene Lokal-Instanz — eigener Host statt Key
            return EffectiveProviderConfig(
                provider=AIProviderType.OLLAMA,
                endpoint=ai_settings.endpoint_url,
                model_name=ai_settings.model_name,
                api_key=None,
                locked_by_server=False,
            )
        api_key = (
            decrypt_secret(ai_settings.encrypted_api_key)
            if ai_settings.encrypted_api_key
            else None
        )
        return EffectiveProviderConfig(
            provider=ai_settings.provider,
            endpoint=None,
            model_name=ai_settings.model_name,
            api_key=api_key,
            locked_by_server=False,
        )

    return None  # keine KI verfügbar -> nur lokale Texterfassung, wie bisher
