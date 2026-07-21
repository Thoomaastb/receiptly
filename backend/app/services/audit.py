"""Schreibt Einträge in die immutable `audit_log`-Tabelle (siehe app/models/audit_log.py)."""

import uuid

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.request_meta import get_client_ip, get_user_agent
from app.models.audit_log import AuditLog
from app.services.household_security import get_or_create_security_settings


async def record_event(
    db: AsyncSession,
    *,
    household_id: uuid.UUID,
    event_type: str,
    user_id: uuid.UUID | None = None,
    request: Request | None = None,
    attempted_username: str | None = None,
    metadata: dict | None = None,
    commit: bool = True,
) -> None:
    """
    `request=None` für Aufrufe ohne HTTP-Request-Kontext (z.B. ein künftiger Batch-/Cron-Job)
    — `ip`/`user_agent` bleiben dann NULL.

    `commit=True` ist bewusst der Default: der Login-Fehlschlag-Pfad in app/api/auth.py
    wirft die HTTPException direkt, ohne vorher db.commit() aufzurufen. Würde record_event()
    dort ohne eigenen Commit aufgerufen, ginge der Audit-Eintrag für genau den
    sicherheitsrelevantesten Fall (fehlgeschlagener Login) beim Request-Ende per Rollback
    stillschweigend verloren. `commit=False` ist nur für Aufrufer gedacht, die den Eintrag
    bewusst in eine bereits laufende Transaktion einbetten und selbst committen wollen.

    `attempted_username` wird vor dem Speichern gegen die haushaltsweite
    `household_security_settings.log_attempted_username`-Einstellung geprüft (Default true
    für Haushalte ohne eigene Zeile, lazy erstellt bei erstem Zugriff) — steht sie auf
    false, wird das Feld hier stillschweigend auf None gesetzt. Der Lookup läuft nur, wenn
    tatsächlich ein `attempted_username` übergeben wurde, um die deutlich häufigeren
    Events ohne dieses Feld nicht mit einem zusätzlichen Query zu belasten.
    """
    if attempted_username is not None:
        security_settings = await get_or_create_security_settings(db, household_id)
        if not security_settings.log_attempted_username:
            attempted_username = None

    entry = AuditLog(
        household_id=household_id,
        event_type=event_type,
        user_id=user_id,
        attempted_username=attempted_username,
        event_metadata=metadata,
        ip=get_client_ip(request) if request is not None else None,
        user_agent=get_user_agent(request) if request is not None else None,
    )
    db.add(entry)
    if commit:
        await db.commit()
    else:
        await db.flush()
