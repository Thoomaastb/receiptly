"""GET/PUT haushaltsweite Sicherheitsrichtlinien — alle Endpoints Admin-only."""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_admin
from app.database import get_db
from app.models.user import User
from app.schemas.security_settings import (
    PasskeyExclusiveGateStatus,
    SecurityPolicyResponse,
    SecurityPolicyUpdate,
)
from app.services.audit import record_event
from app.services.household_security import (
    get_or_create_security_settings,
    get_passkey_exclusive_gate_status,
    lock_household_security,
)

router = APIRouter(prefix="/settings", tags=["security-settings"])

_GATE_MESSAGE = (
    "Passkey-exklusiver Login kann erst aktiviert werden, wenn alle Haushaltsmitglieder "
    "mindestens einen Passkey registriert haben."
)


@router.get("/security-policy", response_model=SecurityPolicyResponse)
async def get_security_policy(
    admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)
) -> SecurityPolicyResponse:
    settings = await get_or_create_security_settings(db, admin.household_id)
    await db.commit()
    return SecurityPolicyResponse.model_validate(settings)


@router.get("/security-policy/passkey-exclusive-gate", response_model=PasskeyExclusiveGateStatus)
async def get_passkey_exclusive_gate(
    admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)
) -> PasskeyExclusiveGateStatus:
    """
    Eigener Read-Endpoint für das Live-Gate-Feedback im Frontend (Konzept 4.1: "Schalter
    mit Live-Gate-Feedback") — unabhängig von einem Aktivierungsversuch abrufbar, damit
    die UI den Schalter schon proaktiv deaktiviert anzeigen kann, bevor der Admin ihn
    überhaupt umlegt.
    """
    missing_members, total_members = await get_passkey_exclusive_gate_status(
        db, admin.household_id
    )
    return PasskeyExclusiveGateStatus(
        eligible=not missing_members,
        total_members=total_members,
        missing_count=len(missing_members),
        missing_usernames=[member.username for member in missing_members],
    )


@router.put("/security-policy", response_model=SecurityPolicyResponse)
async def update_security_policy(
    payload: SecurityPolicyUpdate,
    request: Request,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> SecurityPolicyResponse:
    # lock_household_security() muss vor jeder Prüfung/Zählung erworben werden (Security-
    # Review Phase 4, M2): sonst kann zwischen diesem Gate-Check und dem Commit unten ein
    # paralleler Invite (app/api/auth.py) noch den alten (deaktivierten) Schalterstand
    # sehen und ein neues, passkeyloses Mitglied anlegen, bevor hier auf True committet wird.
    await lock_household_security(db, admin.household_id)
    settings = await get_or_create_security_settings(db, admin.household_id)

    # Precondition-Gate nur beim Übergang aus->an prüfen (Konzept 4.1) — Deaktivieren ist
    # der einzige Rettungsweg bei Passkey-Verlust (Q18) und bleibt deshalb immer erlaubt,
    # unabhängig vom aktuellen Precondition-Status. Serverseitige Durchsetzung zusätzlich
    # zum GET-Status oben (defense in depth) — ein UI-Bug oder ein direkter API-Call darf
    # die Gate-Prüfung nicht umgehen können, da genau das Aussperr-Risiko strukturell
    # ausschließen soll.
    activating_exclusive_login = (
        payload.passkey_exclusive_login and not settings.passkey_exclusive_login
    )
    # Für das Sicherheits-Benachrichtigungssystem (v0.25) muss VOR dem Überschreiben unten
    # verglichen werden, ob sich der Schalter überhaupt ändert (an->aus zählt genauso wie
    # aus->an, anders als activating_exclusive_login oben, das nur die Precondition-Gate-
    # Richtung betrifft).
    passkey_exclusive_login_changed = (
        payload.passkey_exclusive_login != settings.passkey_exclusive_login
    )
    if activating_exclusive_login:
        missing_members, total_members = await get_passkey_exclusive_gate_status(
            db, admin.household_id
        )
        if missing_members:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "message": _GATE_MESSAGE,
                    "eligible": False,
                    "total_members": total_members,
                    "missing_count": len(missing_members),
                    "missing_usernames": [member.username for member in missing_members],
                },
            )

    settings.totp_required_for_household = payload.totp_required_for_household
    settings.audit_retention_days = payload.audit_retention_days
    settings.log_attempted_username = payload.log_attempted_username
    settings.passkey_exclusive_login = payload.passkey_exclusive_login

    if passkey_exclusive_login_changed:
        # commit=False: teilt sich den db.commit() direkt unterhalb dieser Funktion mit
        # (umgekehrter Fall zum sonstigen "Teilt sich den Commit mit record_event(commit=True)"
        # -Kommentar in auth.py/totp.py — hier committet die AUFRUFENDE Funktion, nicht
        # record_event() selbst).
        await record_event(
            db,
            household_id=admin.household_id,
            user_id=admin.id,
            event_type="passkey_exclusive_login_toggled",
            request=request,
            metadata={"enabled": payload.passkey_exclusive_login},
            commit=False,
        )

    await db.commit()
    await db.refresh(settings)
    return SecurityPolicyResponse.model_validate(settings)
