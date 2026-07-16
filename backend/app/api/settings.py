import asyncio
import ipaddress
import socket
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_admin
from app.database import get_db
from app.models.ai_settings import AISettings, AIProviderType
from app.models.user import User
from app.schemas.ai_settings import AISettingsResponse, AISettingsUpdate
from app.services.ai_provider_resolution import resolve_effective_provider
from app.services.crypto import encrypt_secret

router = APIRouter(prefix="/settings", tags=["settings"])


async def _validate_ollama_host(endpoint_url: str) -> None:
    """
    SSRF-Schutz: verhindert, dass ein Haushalts-Admin den Server per endpoint_url auf
    interne Hosts oder Cloud-Metadata-Endpunkte (z.B. 169.254.169.254) zeigen lässt,
    die dann serverseitig ungeprüft per httpx angefragt würden. Prüft nur, wenn der
    Hostname in diesem Prozess tatsächlich auflösbar ist — self-hosted Docker-Compose-
    Servicenamen wie "ollama" lösen hier ggf. (noch) nicht auf, das ist der Normalfall
    und darf nicht kategorisch blockiert werden. Nur ein Treffer in einem privaten/
    link-lokalen/Loopback-/reservierten Range führt zur Ablehnung.
    """
    hostname = urlparse(endpoint_url).hostname
    if not hostname:
        return

    try:
        addr_infos = await asyncio.to_thread(socket.getaddrinfo, hostname, None)
    except socket.gaierror:
        return

    for *_rest, sockaddr in addr_infos:
        ip = ipaddress.ip_address(sockaddr[0])
        if ip.is_private or ip.is_link_local or ip.is_loopback or ip.is_reserved:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ollama-Host löst auf eine private/interne/link-lokale Adresse auf "
                "— aus Sicherheitsgründen nicht erlaubt",
            )


async def _resolve_effective_provider_safe(db: AsyncSession, household_id):
    """
    resolve_effective_provider() kann ValueError werfen, wenn der gespeicherte
    encrypted_api_key nicht mehr entschlüsselbar ist (z.B. rotierter ENCRYPTION_KEY, siehe
    app/services/crypto.py). Anders als in ai_extraction.py (wo das in needs_review
    resultiert) gibt es hier keinen sinnvollen Fallback-Status — die Settings-Seite muss
    trotzdem ladbar bleiben, daher degradiert das auf "kein wirksamer Provider" statt 500.
    """
    try:
        return await resolve_effective_provider(db, household_id)
    except ValueError:
        return None


async def _get_or_create(db: AsyncSession, household_id) -> AISettings:
    result = await db.execute(select(AISettings).where(AISettings.household_id == household_id))
    settings = result.scalar_one_or_none()
    if settings is None:
        # provider=None statt eines Defaults — "kein Haushalts-Provider konfiguriert" ist
        # seit dem Provider-Rework (Migration 0008) ein gültiger, expliziter Zustand.
        settings = AISettings(household_id=household_id, provider=None)
        db.add(settings)
        await db.flush()
    return settings


@router.get("/ai-provider", response_model=AISettingsResponse)
async def get_ai_provider(
    admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)
) -> AISettingsResponse:
    settings = await _get_or_create(db, admin.household_id)
    effective = await _resolve_effective_provider_safe(db, admin.household_id)
    await db.commit()

    locked = effective is not None and effective.locked_by_server
    return AISettingsResponse(
        provider=settings.provider.value if settings.provider else None,
        has_api_key=settings.encrypted_api_key is not None,
        endpoint_url=settings.endpoint_url,
        model_name=settings.model_name,
        locked_by_server=locked,
        effective_provider=effective.provider.value if locked else None,
        effective_model=effective.model_name if locked else None,
    )


@router.put("/ai-provider", response_model=AISettingsResponse)
async def update_ai_provider(
    payload: AISettingsUpdate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> AISettingsResponse:
    """
    Admin-only. Der Key wird nie im Klartext gespeichert oder zurückgegeben — nur
    has_api_key als Boolean. Leeres api_key-Feld lässt einen vorhandenen Key unverändert
    (z.B. wenn nur der Provider gewechselt wird). Bei serverseitig erzwungenem Provider
    (OLLAMA_HOST/AI_HOST in .env) wird die Änderung abgelehnt — die UI zeigt das Formular
    zwar bereits read-only, das Backend darf sich darauf aber nicht allein verlassen.
    """
    effective = await _resolve_effective_provider_safe(db, admin.household_id)
    if effective is not None and effective.locked_by_server:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Der KI-Anbieter ist serverseitig fest konfiguriert und kann hier nicht geändert werden",
        )

    settings = await _get_or_create(db, admin.household_id)
    new_provider = AIProviderType(payload.provider)

    if new_provider == AIProviderType.OLLAMA:
        if not payload.endpoint_url:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ollama/Lokal braucht einen Host (endpoint_url)",
            )
        await _validate_ollama_host(payload.endpoint_url)
        settings.endpoint_url = payload.endpoint_url
        # Lokal, kein Key nötig — alten externen Key nicht stillschweigend weiterverwenden
        settings.encrypted_api_key = None
    else:
        has_key = bool(payload.api_key) or settings.encrypted_api_key is not None
        if not has_key:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{new_provider.value} braucht einen API-Key",
            )
        if payload.api_key:
            settings.encrypted_api_key = encrypt_secret(payload.api_key)
        settings.endpoint_url = None

    settings.provider = new_provider
    settings.model_name = payload.model_name

    await db.commit()
    await db.refresh(settings)

    return AISettingsResponse(
        provider=settings.provider.value if settings.provider else None,
        has_api_key=settings.encrypted_api_key is not None,
        endpoint_url=settings.endpoint_url,
        model_name=settings.model_name,
        locked_by_server=False,
    )
