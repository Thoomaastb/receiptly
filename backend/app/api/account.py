"""
DSGVO-Endpoints: Daten-Export (Art. 15/20) + Konto-Löschung (Art. 17, 14-Tage-Karenzzeit
mit Reaktivierung). Siehe concepts/konto-loeschen-datenexport.md für den vollen
fachlichen/rechtlichen Kontext. Löschantrag/Reaktivierung teilen sich die Kernlogik mit
app/services/account_deletion.py (Stufe A) bzw. app/scripts/account_deletion_teardown.py
(Stufe B, per täglichem Scheduler-Job).
"""

import tempfile
from datetime import date
from pathlib import Path

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.background import BackgroundTask

from app.api.auth import _build_user_response
from app.auth.dependencies import require_totp_enrolled
from app.auth.pending_reactivation import (
    PENDING_REACTIVATION_COOKIE_NAME,
    destroy_pending_reactivation,
    get_pending_reactivation_user_id,
)
from app.auth.rate_limit import check_rate_limit
from app.auth.session import create_session, invalidate_other_sessions
from app.auth.webauthn_challenge import store_authentication_challenge
from app.database import get_db
from app.models.user import User
from app.models.webauthn_credential import WebauthnCredential
from app.schemas.account import AccountDeletionRequest, AccountDeletionResponse
from app.schemas.auth import UserResponse
from app.schemas.webauthn import WebauthnAuthenticateOptionsResponse
from app.services import webauthn as webauthn_service
from app.services.account_deletion import (
    AdminGateBlockedError,
    request_deletion,
    verify_active_login_factor,
)
from app.services.audit import record_event
from app.services.data_export import build_export_zip

router = APIRouter(prefix="/account", tags=["account"])


@router.get("/export")
async def export_account_data(
    user: User = Depends(require_totp_enrolled), db: AsyncSession = Depends(get_db)
) -> FileResponse:
    """
    DSGVO-Datenexport (Art. 15/20, Konzept 3.1) als ZIP-Download — synchron/streamend über
    eine Temp-Datei (Konzept Q8, für die Zielgröße 2-Personen-Haushalt ausreichend). Die
    Temp-Datei wird nach Auslieferung per BackgroundTask entfernt.
    """
    with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmp_file:
        dest_path = Path(tmp_file.name)

    await build_export_zip(db, user, dest_path)

    filename = f"receiptly-export-{user.username}-{date.today().isoformat()}.zip"
    return FileResponse(
        dest_path,
        filename=filename,
        media_type="application/zip",
        background=BackgroundTask(lambda: dest_path.unlink(missing_ok=True)),
    )


@router.post(
    "/deletion/reauth/passkey-options", response_model=WebauthnAuthenticateOptionsResponse
)
async def deletion_reauth_passkey_options(
    user: User = Depends(require_totp_enrolled), db: AsyncSession = Depends(get_db)
) -> WebauthnAuthenticateOptionsResponse:
    """
    Dünner Wrapper um die WebAuthn-Options-Generierung für die Löschbestätigung — anders
    als /webauthn/authenticate/options (Login, User noch unbekannt) ist der User hier
    bereits über eine bestehende Session bekannt: die Optionen sind direkt auf seine
    eigenen Credential-IDs eingeschränkt, kein Username-Lookup/Enumeration-Schutz nötig.
    Nur relevant, wenn passkey_exclusive_login aktiv ist — die eigentliche Durchsetzung
    (Faktor-Wahl) passiert in verify_active_login_factor().
    """
    result = await db.execute(
        select(WebauthnCredential.credential_id).where(WebauthnCredential.user_id == user.id)
    )
    allow_credential_ids = [row[0] for row in result.all()]

    options_json, challenge = webauthn_service.generate_authentication_options(
        allow_credential_ids=allow_credential_ids
    )
    options_id = await store_authentication_challenge(user.id, challenge)
    return WebauthnAuthenticateOptionsResponse(options=options_json, options_id=options_id)


@router.post("/deletion", response_model=AccountDeletionResponse)
async def request_account_deletion(
    payload: AccountDeletionRequest,
    request: Request,
    user: User = Depends(require_totp_enrolled),
    db: AsyncSession = Depends(get_db),
) -> AccountDeletionResponse:
    """
    Stufe A der Konto-Löschung (Konzept 3.2): Rate-Limit → serverseitige Tipp-Bestätigung
    → Re-Auth des aktiven Login-Faktors → Löschantrag (scheduled_deletion_at + 14 Tage) →
    Response aufbauen → danach ALLE Sessions des Users invalidieren (auch die aktuelle,
    Konzept 3.2 Stufe A.3) — bewusst erst NACH dem Response-Aufbau, sonst wäre die eigene
    laufende Anfrage bereits mitten in der Ausführung unauthentifiziert.
    """
    await check_rate_limit("account_deletion_confirm", str(user.id), 5, 3600)

    if payload.confirmation_text not in {user.username, "LÖSCHEN"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bestätigungstext stimmt nicht überein — bitte Nutzernamen oder LÖSCHEN eingeben.",
        )

    await verify_active_login_factor(db, user, payload)

    try:
        await request_deletion(db, user, request)
    except AdminGateBlockedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Du bist der einzige Admin — ernenne zuerst ein anderes Mitglied zum Admin.",
        ) from exc

    response = AccountDeletionResponse(scheduled_deletion_at=user.scheduled_deletion_at)

    await invalidate_other_sessions(user.id, keep_raw_token=None)
    return response


@router.post("/reactivate", response_model=UserResponse)
async def reactivate_account(
    response: Response,
    request: Request,
    db: AsyncSession = Depends(get_db),
    pending_cookie: str | None = Cookie(default=None, alias=PENDING_REACTIVATION_COOKIE_NAME),
) -> UserResponse:
    """
    Bricht die Karenzzeit ab — bewusst OHNE Auth-Dependency: Stufe A hat beim Antrag
    bereits ausnahmslos alle Sessions zerstört (siehe request_account_deletion()). Der
    Pending-Reactivation-Cookie (gesetzt von check_reactivation_required() während eines
    Login-Versuchs) ist der einzige Nachweis, dass die Login-Faktoren bereits vollständig
    geprüft wurden.
    """
    user_id = await get_pending_reactivation_user_id(pending_cookie)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Reaktivierung abgelaufen oder ungültig — bitte erneut einloggen.",
        )

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None or user.scheduled_deletion_at is None:
        await destroy_pending_reactivation(pending_cookie, response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Reaktivierung abgelaufen oder ungültig — bitte erneut einloggen.",
        )

    await check_rate_limit("account_reactivate", str(user_id), 5, 900)

    user.scheduled_deletion_at = None
    await record_event(
        db,
        household_id=user.household_id,
        user_id=user.id,
        event_type="account_reactivated",
        request=request,
    )

    await create_session(user.id, response, request)
    await destroy_pending_reactivation(pending_cookie, response)
    return await _build_user_response(db, user)
