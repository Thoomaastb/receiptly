"""
TOTP-Enrollment-/Verwaltungs-Endpoints — abgegrenzt vom Login-Flow (POST /auth/login/totp
liegt weiterhin in app/api/auth.py, da er zum Pre-Auth-Login-Ablauf gehört, nicht zur
Verwaltung einer bestehenden Session). Alle Endpoints hier setzen eine bestehende Session
voraus (get_current_user).
"""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.auth.rate_limit import check_rate_limit
from app.auth.security import verify_password
from app.database import get_db
from app.models.totp_recovery_code import TotpRecoveryCode
from app.models.user import User, UserRole
from app.schemas.totp import (
    TotpConfirmRequest,
    TotpEnrollResponse,
    TotpReauthRequest,
    TotpRecoveryCodesResponse,
)
from app.services import totp
from app.services.audit import record_event
from app.services.crypto import decrypt_secret, encrypt_secret

router = APIRouter(prefix="/auth/totp", tags=["totp"])


async def _reverify(user: User, payload: TotpReauthRequest) -> None:
    """
    Re-Verifizierung analog zum change_password()-Reauth-Muster (app/api/auth.py):
    aktuelles Passwort UND/ODER gültiger TOTP-Code — mindestens eines von beidem muss
    stimmen, bevor /disable oder /recovery-codes/regenerate etwas ändern.
    """
    password_ok = payload.current_password is not None and verify_password(
        payload.current_password, user.password_hash
    )
    code_ok = False
    if payload.code and user.totp_secret:
        try:
            code_ok = totp.verify_code(decrypt_secret(user.totp_secret), payload.code)
        except ValueError:
            code_ok = False

    if not password_ok and not code_ok:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Re-Verifizierung fehlgeschlagen"
        )


async def _replace_recovery_codes(db: AsyncSession, user: User) -> list[str]:
    """Löscht alle bestehenden Codes und legt einen neuen Satz an (Delete-all+Insert-all, kein In-Place-Edit)."""
    await db.execute(delete(TotpRecoveryCode).where(TotpRecoveryCode.user_id == user.id))
    plain_codes = totp.generate_recovery_codes()
    for code in plain_codes:
        db.add(TotpRecoveryCode(user_id=user.id, code_hash=totp.hash_recovery_code(code)))
    return plain_codes


@router.post("/enroll", response_model=TotpEnrollResponse)
async def enroll_totp(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> TotpEnrollResponse:
    """
    Generiert ein neues Secret und speichert es bereits (Fernet-verschlüsselt) zwischen —
    `totp_enabled` bleibt false, bis /confirm einen gültigen Code liefert (verhindert
    Aussperren durch Fehlkonfiguration, siehe Konzept 4.2). Ein erneuter Aufruf überschreibt
    weiterhin ein zuvor UNBESTÄTIGTES Secret (z.B. abgebrochene Einrichtung, neuer QR-Code
    nötig) — das ist gewollt und braucht keine Reauth.

    Ist TOTP bereits aktiv, lehnt dieser Endpoint hingegen ab (400) statt das aktive Secret
    kommentarlos zu überschreiben (Security-Hardening-Nachbesserung): ohne diese Sperre
    könnte eine gekaperte Session das aktive Secret unbemerkt ersetzen, ohne die Reauth zu
    durchlaufen, die /disable und /recovery-codes/regenerate über _reverify() verlangen.
    Nicht-Admins müssen jetzt zuerst /disable (reauth-pflichtig) aufrufen, bevor sie neu
    einrichten können. Für Admins (die /disable laut Konzept 4.1 nicht nutzen dürfen)
    bedeutet das: kein Re-Enrollment-Weg über /enroll mehr, solange TOTP aktiv ist — das ist
    beabsichtigt und deckt sich mit dem Angriffsszenario, das hier verhindert werden soll.
    Ein Wiederherstellungsweg bei verlorener Authenticator-App bleibt über die Recovery-
    Codes bestehen (/auth/login/totp akzeptiert die weiterhin).
    """
    if user.totp_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="TOTP ist bereits aktiv — zum Neueinrichten zuerst /auth/totp/disable aufrufen.",
        )

    await check_rate_limit("totp_enroll", str(user.id), 10, 3600)

    secret = totp.generate_secret()
    user.totp_secret = encrypt_secret(secret)
    await db.commit()

    return TotpEnrollResponse(secret=secret, qr_svg=totp.generate_qr_svg(secret, user.username))


@router.post("/confirm", response_model=TotpRecoveryCodesResponse)
async def confirm_totp(
    payload: TotpConfirmRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TotpRecoveryCodesResponse:
    """
    Bestätigt das in /enroll zwischengespeicherte Secret mit einem gültigen Code, aktiviert
    TOTP und generiert die Recovery-Codes — Klartext nur in dieser einen Antwort, danach
    nur noch Hashes in der DB.
    """
    await check_rate_limit("totp_confirm", str(user.id), 10, 3600)

    if not user.totp_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Keine Einrichtung gestartet — zuerst /auth/totp/enroll aufrufen.",
        )
    if user.totp_enabled:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="TOTP ist bereits aktiv.")

    if not totp.verify_code(decrypt_secret(user.totp_secret), payload.code):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Ungültiger Code")

    user.totp_enabled = True
    plain_codes = await _replace_recovery_codes(db, user)

    await record_event(
        db, household_id=user.household_id, user_id=user.id, event_type="totp_enabled", request=request
    )

    return TotpRecoveryCodesResponse(recovery_codes=plain_codes)


@router.post("/disable", status_code=status.HTTP_204_NO_CONTENT)
async def disable_totp(
    payload: TotpReauthRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Für Admins hart gesperrt (403) — TOTP-Pflicht ist für Admins nicht abwählbar (Konzept 4.1)."""
    if user.role == UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="TOTP ist für Admins verpflichtend und kann nicht deaktiviert werden.",
        )

    await check_rate_limit("totp_disable", str(user.id), 5, 3600)
    await _reverify(user, payload)

    user.totp_enabled = False
    user.totp_secret = None
    await db.execute(delete(TotpRecoveryCode).where(TotpRecoveryCode.user_id == user.id))

    await record_event(
        db, household_id=user.household_id, user_id=user.id, event_type="totp_disabled", request=request
    )


@router.post("/recovery-codes/regenerate", response_model=TotpRecoveryCodesResponse)
async def regenerate_recovery_codes(
    payload: TotpReauthRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TotpRecoveryCodesResponse:
    if not user.totp_enabled:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="TOTP ist nicht aktiv.")

    await check_rate_limit("totp_recovery_regenerate", str(user.id), 5, 3600)
    await _reverify(user, payload)

    plain_codes = await _replace_recovery_codes(db, user)

    await record_event(
        db,
        household_id=user.household_id,
        user_id=user.id,
        event_type="recovery_codes_regenerated",
        request=request,
    )

    return TotpRecoveryCodesResponse(recovery_codes=plain_codes)
